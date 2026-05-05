import json
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from loguru import logger

from src.core.config import settings


class AIMappingError(Exception):
    """Custom exception for AI mapping failures that should be retried or split."""

    def __init__(self, message, is_retryable=True):
        super().__init__(message)
        self.is_retryable = is_retryable


class AIMapper:
    def __init__(self, client: genai.Client | None = None):
        self.target_labels = settings.TARGET_LABELS
        # Persistent executor to avoid blocking on hung threads during context exit
        self.executor = ThreadPoolExecutor(max_workers=20)
        self._shutdown_lock = threading.Lock()
        self._is_shutdown = False

        if client:
            self.client = client
        else:
            self.client = genai.Client(
                api_key=settings.GEMINI_API_KEY, http_options=types.HttpOptions(timeout=60000)
            )

    def _get_system_instruction(self, market: str) -> str:
        target_labels = self.target_labels
        market_context = ""

        if market in ["EDINET", "JP_EDINET"]:
            target_labels = settings.JQUANTS_V2_LABELS
            market_context = """
            MARKET CONTEXT: JAPAN (EDINET / J-Quants)
            - You are mapping raw Japanese EDINET XBRL tags to J-Quants V2 schema fields.
            - Focus on the Japanese name and the Taxonomy ID (e.g., jppfs_cor:NetSales).
            - J-Quants V2 fields (e.g., NetSales, OperatingProfit) are specific. Use them exactly.
            - If the tag represents 'Net Income' or 'Profit for the year', map it to 'Profit'.
            - If the tag represents 'EPS', map it to 'EarningsPerShare'.
            """
        elif market in ["US", "SEC"]:
            market_context = """
            MARKET CONTEXT: US (SEC / EDGAR)
            - You are mapping US-GAAP tags to standardized labels.
            - Pay attention to consolidated vs. non-consolidated if specified in the tag name.
            """

        return f"""
        You are a professional financial data analyst specializing in XBRL and GAAP standards.
        Your task is to map a market-specific financial tag to the MOST APPROPRIATE standardized
        target label from the provided list.

        {market_context}

        VALID TARGET LABELS (Pick ONE):
        {", ".join(target_labels)}, Other

        CRITICAL INSTRUCTIONS:
        1. YOU MUST SELECT A LABEL FROM THE 'VALID TARGET LABELS' LIST ABOVE.
        2. If no label fits well, you MUST use "Other".
        3. DO NOT return placeholder strings like "mapped_label" or "target_label" as the value.
        4. OUTPUT ONLY A VALID JSON OBJECT matching the requested schema.
        5. Provide a brief, concise reasoning for your choice.
        6. Do not enter an infinite loop. If you cannot find a match, stop and return "Other".
        """  # noqa: S608

    def map_tag(self, market: str, tag: str, description: str, session_id: str) -> dict[str, Any]:
        """Maps a single tag using the batch interface."""
        models = settings.LIGHT_GOOGLE_AI_MODELS
        results = self.map_tags_batch(market, [(tag, description)], models[0], session_id)
        return results[0] if results else {}

    def _get_batch_response_schema(self, valid_labels: list[str]) -> dict[str, Any]:
        # Include "Other" as a valid option in the enum
        enum_values = valid_labels + ["Other"]
        return {
            "type": "OBJECT",
            "properties": {
                "mappings": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "tag_id": {"type": "STRING"},
                            "mapped_label": {"type": "STRING", "enum": enum_values},
                            "reasoning": {"type": "STRING"},
                            "confidence": {"type": "NUMBER"},
                        },
                        "required": ["tag_id", "mapped_label", "reasoning", "confidence"],
                    },
                }
            },
            "required": ["mappings"],
        }

    def _clean_json_response(self, text: str) -> str:
        """Removes common LLM artifacts from the response before parsing."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    def map_tags_batch(
        self, market: str, tags: list[tuple], model_name: str, session_id: str
    ) -> list[dict[str, Any]]:
        """
        True Batching: Processes multiple tags in a SINGLE API call.
        """
        if not tags:
            return []

        tags_data = [{"id": f"T{i}", "tag": t, "desc": d} for i, (t, d) in enumerate(tags)]
        tags_json = json.dumps(tags_data, ensure_ascii=False)

        prompt = f"""
        Market: {market}
        Provide mappings for the following list of financial tags.

        Tags to map:
        {tags_json}
        """

        # Determine valid labels for this market for schema enforcement
        valid_labels = settings.JQUANTS_V2_LABELS if market in ["EDINET", "JP_EDINET"] else settings.TARGET_LABELS

        try:
            config = types.GenerateContentConfig(
                system_instruction=self._get_system_instruction(market),
                response_mime_type="application/json",
                response_schema=self._get_batch_response_schema(valid_labels),
                temperature=settings.GEMINI_TEMPERATURE,
                http_options=types.HttpOptions(timeout=180000),
            )
            response = self.client.models.generate_content(
                model=model_name, contents=prompt, config=config
            )

            raw_text = response.text
            try:
                # Basic cleaning
                json_str = self._clean_json_response(raw_text)

                # Robust extraction: find the first '{' and the last '}'
                start_idx = json_str.find("{")
                end_idx = json_str.rfind("}")

                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_str = json_str[start_idx : end_idx + 1]

                batch_data = json.loads(json_str)
                batch_results = batch_data.get("mappings", [])
            except Exception as jse:
                # Sanitize log: truncate long output
                preview_len = 500
                display_text = (
                    raw_text[:preview_len] + "..." if len(raw_text) > preview_len else raw_text
                )
                logger.error(f"JSON Parsing failed for {model_name}. Preview: {display_text}")
                raise AIMappingError(f"JSON Parse Failure: {jse}", is_retryable=True) from jse

            final_results = []
            for i, res in enumerate(batch_results):
                if i >= len(tags):
                    break  # Safety check

                mapped_label = res["mapped_label"]
                # Strict validation: only accept labels in the appropriate target set or "Other"
                valid_labels = (
                    settings.JQUANTS_V2_LABELS
                    if market in ["EDINET", "JP_EDINET"]
                    else self.target_labels
                )
                if mapped_label not in valid_labels and mapped_label != "Other":
                    logger.warning(
                        f"AI returned invalid label '{mapped_label}' for market '{market}' "
                        f"tag '{tags[i][0]}'. Normalizing to 'Other'."
                    )
                    mapped_label = "Other"

                tag_orig, _ = tags[i]
                final_results.append(
                    {
                        "source_tag": f"{market}:{tag_orig}",
                        "mapped_label": mapped_label,
                        "model": model_name,
                        "reasoning": res["reasoning"],
                        "confidence": res.get("confidence", 0.0),
                    }
                )

            return final_results

        except Exception as e:
            # Detect 500 or 429 and specifically flag as retryable
            error_str = str(e).upper()
            is_retryable = any(term in error_str for term in ["500", "504", "INTERNAL", "DEADLINE", "429", "RATE", "TIMEOUT"])

            if is_retryable:
                logger.warning(f"Transient AI API failure ({model_name}): {e}")
            else:
                logger.error(f"Non-retryable AI API failure ({model_name}): {e}")

            raise AIMappingError(
                f"API Failure ({model_name}): {e}", is_retryable=is_retryable
            ) from e

    def map_tags_bulk(
        self,
        market: str,
        tags_with_desc: list[tuple],
        session_id: str,
        batch_size: int | None = None,
        timeout: int = 120,
    ) -> list[dict[str, Any]]:
        """
        Resilient Bulk Mapping: Automatically splits batches on failure.
        """
        if not tags_with_desc:
            return []

        with self._shutdown_lock:
            if self._is_shutdown:
                logger.error("AIMapper is already shut down. Cannot perform bulk mapping.")
                return []

        if batch_size is None:
            batch_size = settings.AI_MAPPING_BATCH_SIZE

        available_models = settings.LIGHT_GOOGLE_AI_MODELS
        max_parallelism = settings.AI_MAX_PARALLELISM
        results = []

        work_queue = deque(
            [tags_with_desc[i : i + batch_size] for i in range(0, len(tags_with_desc), batch_size)]
        )

        logger.info(f"Starting resilient mapping of {len(tags_with_desc)} tags with {max_parallelism} parallel slots...")

        while work_queue:
            # Pop up to max_parallelism batches
            current_batches = []
            for _ in range(min(len(work_queue), max_parallelism)):
                current_batches.append(work_queue.popleft())

            future_to_batch = {}
            future_to_model = {}

            with self._shutdown_lock:
                if self._is_shutdown:
                    break

                for i, batch in enumerate(current_batches):
                    # Round-robin through available models
                    model_name = available_models[i % len(available_models)]
                    try:
                        future = self.executor.submit(
                            self.map_tags_batch, market, batch, model_name, session_id
                        )
                        future_to_batch[future] = batch
                        future_to_model[future] = model_name
                    except RuntimeError:
                        work_queue.append(batch)
                        break

            # Process futures as they complete
            done, not_done = wait(future_to_batch.keys(), timeout=timeout)

            # Handle completed
            for future in done:
                batch = future_to_batch[future]
                try:
                    res_list = future.result()
                    results.extend(res_list)
                    logger.info(f"  [Progress] Saved {len(res_list)} tags")
                except Exception as exc:
                    is_retryable = getattr(exc, "is_retryable", False)
                    # We also treat JSON Parsing errors as retryable (hallucinations/transients)
                    if "JSON Parse Failure" in str(exc) or "JSON Parsing failed" in str(exc):
                        is_retryable = True
                    if len(batch) > 1:
                        mid = len(batch) // 2
                        work_queue.append(batch[:mid])
                        work_queue.append(batch[mid:])
                        logger.warning(f"  [Resilience] Batch failed ({exc}). SPLITTING.")
                        if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                            time.sleep(5)
                    elif is_retryable:
                        work_queue.append(batch)
                        logger.warning(f"  [Resilience] Single tag failed ({exc}). RETRYING.")
                        time.sleep(1)
                    else:
                        logger.error(f"  [Critical] Tag failed permanently: {exc}")

            # Handle hung: WE ABANDON THEM. The executor threads stay busy but we don't wait.
            for future in not_done:
                batch = future_to_batch[future]
                future.cancel()  # Usually does nothing if running
                if len(batch) > 1:
                    mid = len(batch) // 2
                    work_queue.append(batch[:mid])
                    work_queue.append(batch[mid:])
                    logger.warning("  [Resilience] Batch ABANDONED (HUNG). SPLITTING for retry.")
                else:
                    work_queue.append(batch)
                    logger.warning("  [Resilience] Single tag ABANDONED (HUNG). RETRYING.")

        return results

    def shutdown(self, wait=True):
        """Safely shut down the executor."""
        with self._shutdown_lock:
            if not self._is_shutdown:
                self._is_shutdown = True
                self.executor.shutdown(wait=wait)
                logger.info("AIMapper Executor shut down.")


if __name__ == "__main__":
    load_dotenv()
    mapper = AIMapper()
    # Test bulk mapping
    test_tags = [
        ("us-gaap:NetIncomeLoss", "Net income"),
        ("us-gaap:Revenues", "Total revenues"),
        ("us-gaap:Assets", "Total assets"),
    ]
    results = mapper.map_tags_bulk("US", test_tags, "bulk-test-session")
    for r in results:
        print(r)
