import logging
from typing import Any

from src.mappers.ai_mapper import AIMapper

logger = logging.getLogger(__name__)


class EDINETMapper:
    """
    Stage 1 AI Mapping: Maps raw EDINET tags to canonical labels.
    Ensures every mapping decision is traceable.
    """

    def __init__(self, ai_mapper: AIMapper | None = None):
        self.ai_mapper = ai_mapper or AIMapper()
        logger.info("EDINETMapper initialized.")

    def map_edinet_tags(self, tags: list[tuple], session_id: str) -> list[dict[str, Any]]:
        """
        Maps raw EDINET tags to standard labels.
        tags: [(Element ID, Element Name), ...]
        """
        if not tags:
            logger.info("No tags provided for mapping.")
            return []

        logger.info(f"[AI-MAP] Starting Stage 1 mapping for {len(tags)} tags. session={session_id}")
        try:
            results = self.ai_mapper.map_tags_bulk("JP_EDINET", tags, session_id)
            logger.info(f"[AI-MAP] Mapping complete. Successfully mapped {len(results)} tags.")
            return results
        except Exception as e:
            logger.error(f"Critical failure in AI Mapping stage: {e}", exc_info=True)
            raise RuntimeError("AI Mapping Pipeline Failure") from e

    def normalize_facts(
        self,
        raw_facts: list[dict[str, Any]],
        tag_mapping: dict[str, str],
        metadata: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Transforms raw facts into canonical schema with full metadata tracing.
        """
        normalized = []
        logger.info(f"[NORM] Normalizing {len(raw_facts)} facts for {metadata.get('code')}")

        for fact in raw_facts:
            element_id = fact["id"]
            mapped_label = tag_mapping.get(element_id)

            if not mapped_label:
                # Log unmapped tags at debug level to avoid log spam,
                # but keep count for visibility.
                continue

            try:
                norm_fact = {
                    "code": str(metadata["code"]),
                    "disclosed_date": metadata["disclosed_date"],
                    "fiscal_year": metadata.get("fiscal_year"),
                    "fiscal_period": metadata.get("fiscal_period"),
                    "taxonomy": "JP_EDINET",
                    "tag": element_id,
                    "label": mapped_label,
                    "value": fact["value"],
                    "unit": fact.get("unit", "JPY"),
                    "accession_number": metadata["accession_number"],
                    "session_id": metadata["session_id"],
                }
                normalized.append(norm_fact)
            except KeyError as e:
                logger.error(f"Missing required metadata key: {e}")
                raise ValueError(f"Normalization failed: Metadata incomplete ({e})") from e

        logger.info(f"[NORM] Normalization complete. Produced {len(normalized)} canonical facts.")
        return normalized
