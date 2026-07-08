import concurrent.futures
import datetime
import gc
import logging

import edinet_tools
import pandas as pd
from loguru import logger

from src.datalake.shared.domain.contracts import CompanyFact, FilingMetadata, NarrativeBlock
from src.datalake.shared.infra.config import settings
from src.datalake.shared.infra.db import db_manager
from src.datalake.shared.infra.trace import with_context
from src.datalake.shared.infra.rate_limit import edinet_rate_limit

from .csv_parser import get_csv_from_edinet, parse_edinet_csv
from .writer import DatabaseWriter

# Suppress edinet_tools LLM warning before it gets imported
logging.getLogger().setLevel(logging.ERROR)


class DataIngestor:
    def __init__(self):
        if not settings.EDINET_API_KEY:
            logger.warning("EDINET_API_KEY is not set. API calls will fail.")
        edinet_tools.configure(api_key=settings.EDINET_API_KEY)
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.writer = DatabaseWriter()

    def process_docs_concurrently(self, docs, session_id, max_workers, bypass_manifest_check=False):
        if not docs:
            logger.info("No documents provided for processing.")
            return

        import queue
        import threading

        completed_doc_ids = set()
        if not bypass_manifest_check:
            logger.debug(
                f"Querying existing filings and manifest status for {len(docs)} candidates..."
            )
            with db_manager.connect_master(read_only=True) as conn:
                try:
                    existing_doc_ids = {
                        row[0]
                        for row in conn.execute("SELECT doc_id FROM registry_db.filings").fetchall()
                    }
                    try:
                        successful_doc_ids = {
                            row[0]
                            for row in conn.execute(
                                "SELECT doc_id FROM ingestion_log WHERE status = 'SUCCESS'"
                            ).fetchall()
                        }
                    except Exception:
                        successful_doc_ids = set()

                    completed_doc_ids = existing_doc_ids.union(successful_doc_ids)
                    logger.debug(
                        f"Found {len(completed_doc_ids)} already completed filings/logs in DB."
                    )
                except Exception as e:
                    logger.error(f"Failed to query existing filings/manifest: {e}", exc_info=True)
                    raise

        TARGET_FORM_CODES = {"030000", "030001", "043000", "043001", "040000", "040001"}
        docs_to_process = [
            doc
            for doc in docs
            if (bypass_manifest_check or doc._data.get("docID") not in completed_doc_ids)
            and (doc._data.get("formCode") in TARGET_FORM_CODES)
        ]

        if not docs_to_process:
            logger.info("All documents are up-to-date. Skipping ingestion.")
            return

        logger.info(f"Processing {len(docs_to_process)} documents (Session: {session_id})...")

        # Bounded queue to prevent memory growth (holds raw downloaded ZIP/CSV bytes)
        download_queue = queue.Queue(maxsize=15)

        # Start the database writer
        self.writer.start()

        # Counter for progress logging
        processed_count = [0]
        progress_lock = threading.Lock()

        def download_task(doc, ticker):
            doc_id = doc._data.get("docID")
            try:
                # 1. Download ZIP bytes
                zip_bytes = None
                if hasattr(doc, "fetch"):
                    edinet_rate_limit.check_and_wait()
                    zip_bytes = doc.fetch()

                # 2. Download CSV bytes if flagged
                csv_bytes = None
                if doc._data.get("csvFlag") == "1":
                    edinet_rate_limit.check_and_wait()
                    csv_bytes = get_csv_from_edinet(doc_id, settings.EDINET_API_KEY)

                download_queue.put((doc, zip_bytes, csv_bytes, ticker))
                logger.debug(f"Successfully downloaded raw data for {doc_id}")
            except Exception as err:
                logger.error(f"Download failed for {doc_id}: {err}", exc_info=True)
                log_data = (
                    doc_id,
                    "FAILED",
                    datetime.datetime.now(),
                    f"Download failed: {err}",
                )
                self.writer.put("log", log_data)

        def parser_worker_loop():
            while True:
                item = download_queue.get()
                if item is None:
                    # Propagate termination marker
                    download_queue.put(None)
                    break

                doc, zip_bytes, csv_bytes, ticker = item
                doc_id = doc._data.get("docID")
                try:
                    # Monkeypatch doc.fetch to return pre-downloaded bytes
                    doc.fetch = lambda: zip_bytes

                    # Process the document
                    result, status_info = self._process_single_doc(
                        doc, ticker, session_id, csv_bytes=csv_bytes
                    )

                    if result:
                        self.writer.put("ingest", result)
                        logger.debug(f"Queued {doc_id} for DB write.")
                    else:
                        logger.warning(f"Processing empty for {doc_id}: {status_info}")

                    log_data = (
                        doc_id,
                        status_info["status"],
                        datetime.datetime.now(),
                        status_info.get("error"),
                    )
                    self.writer.put("log", log_data)
                except Exception as err:
                    logger.error(f"Parser error for {doc_id}: {err}", exc_info=True)
                    log_data = (
                        doc_id,
                        "PARTIAL_FAIL",
                        datetime.datetime.now(),
                        f"Parser error: {err}",
                    )
                    self.writer.put("log", log_data)
                finally:
                    with progress_lock:
                        processed_count[0] += 1
                        if processed_count[0] % 10 == 0:
                            logger.info(
                                f"Progress: {processed_count[0]}/{len(docs_to_process)} (Queued)"
                            )
                    download_queue.task_done()

        # Start parser threads
        num_parsers = max_workers if max_workers > 0 else 1
        parser_threads = []
        for i in range(num_parsers):
            t = threading.Thread(target=parser_worker_loop, name=f"ParserWorker-{i}", daemon=True)
            t.start()
            parser_threads.append(t)

        try:
            # Download concurrently with a thread pool (max 3 downloaders)
            num_downloaders = min(3, len(docs_to_process))
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=num_downloaders, thread_name_prefix="DownloaderPool"
            ) as downloader_executor:
                futures = [
                    downloader_executor.submit(
                        with_context(download_task), doc, doc._data.get("secCode", "0000")
                    )
                    for doc in docs_to_process
                ]
                concurrent.futures.wait(futures)

            # Signal parser threads to terminate
            download_queue.put(None)

            # Wait for all parser threads to consume remaining items and exit
            for t in parser_threads:
                t.join()

        finally:
            logger.info("Finishing ingestion. Waiting for background writers...")
            self.writer.stop()
            gc.collect()

    def backfill_missing_data(self, max_workers: int = 5):
        """Identifies and processes filings missing narratives or facts."""
        logger.info("Starting backfill for missing data...")

        with db_manager.connect_master(read_only=True) as conn:
            query = """
                SELECT f.doc_id, f.sec_code, f.submit_datetime
                FROM registry_db.filings f
                LEFT JOIN narr_db.narratives n ON f.doc_id = n.doc_id
                LEFT JOIN (
                    SELECT doc_id FROM facts_db.company_facts GROUP BY doc_id
                ) c ON f.doc_id = c.doc_id
                WHERE
                    (n.doc_id IS NULL OR c.doc_id IS NULL)
                    AND f.form_code IN ('030000', '030001', '043000', '043001', '040000', '040001')
            """
            missing = conn.execute(query).fetchall()

        if not missing:
            logger.info("No missing data identified for backfill.")
            return

        logger.info(f"Identified {len(missing)} documents requiring backfill.")

        # Group by date to minimize API calls
        by_date = {}
        for did, sc, dt in missing:
            d = pd.to_datetime(dt).date()
            if d not in by_date:
                by_date[d] = []
            by_date[d].append((did, sc))

        TARGET_FORM_CODES = {"030000", "030001", "043000", "043001", "040000", "040001"}
        docs_to_process = []
        for d, items in by_date.items():
            try:
                all_docs_on_date = edinet_tools.documents(date=d)
                target_ids = {did for did, sc in items}
                for doc in all_docs_on_date:
                    if doc._data.get("docID") in target_ids and (
                        doc._data.get("formCode") in TARGET_FORM_CODES
                    ):
                        sc = next(sc for did, sc in items if did == doc._data.get("docID"))
                        docs_to_process.append((doc, sc))
            except Exception as e:
                logger.error(f"Failed to fetch docs for backfill on {d}: {e}", exc_info=True)

        if not docs_to_process:
            logger.warning("Could not retrieve any document objects for backfill.")
            return

        self._execute_backfill_queue(docs_to_process, max_workers)

    def _execute_backfill_queue(self, docs_to_process, max_workers):
        docs = []
        for doc, sc in docs_to_process:
            doc._data["secCode"] = sc
            docs.append(doc)

        self.process_docs_concurrently(docs, "backfill", max_workers, bypass_manifest_check=True)
        logger.info(f"Backfill completed. Processed {len(docs_to_process)} documents.")

    def _process_single_doc(self, doc, ticker, session_id, csv_bytes=None):
        doc_id = doc._data.get("docID")
        status_info = {"status": "SUCCESS", "error": None}
        try:
            facts = self._extract_facts(doc, ticker, session_id, csv_bytes=csv_bytes)
            if facts is None and doc._data.get("csvFlag") == "1":
                status_info = {"status": "PARTIAL_FAIL", "error": "CSV content returned None"}
                return None, status_info

            metadata = self._extract_metadata(doc, ticker, session_id)
            narratives = self._extract_narratives(doc, ticker, session_id)

            if not narratives and (doc._data.get("formCode") or "").startswith(
                ("030000", "043000")
            ):
                status_info["status"] = "PARTIAL_FAIL"
                status_info["error"] = "No narrative blocks extracted"

            valid_meta = FilingMetadata(**metadata)
            valid_facts = [CompanyFact(**f) for f in facts or []]
            valid_narrs = [NarrativeBlock(**n) for n in narratives or []]

            result = {
                "metadata": valid_meta.model_dump(),
                "narratives": [n.model_dump() for n in valid_narrs],
                "facts": [f.model_dump() for f in valid_facts],
            }
            return result, status_info
        except Exception as e:
            logger.error(f"Contract validation failed for {doc_id}: {e}", exc_info=True)
            status_info = {"status": "PARTIAL_FAIL", "error": str(e)}
            return None, status_info

    def _extract_metadata(self, doc, ticker, session_id):
        data = doc._data
        return {
            "doc_id": data.get("docID"),
            "edinet_code": data.get("edinetCode"),
            "sec_code": ticker,
            "filer_name": data.get("filerName"),
            "doc_description": data.get("docDescription"),
            "submit_datetime": data.get("submitDateTime"),
            "form_code": data.get("formCode"),
            "doc_type_code": data.get("docTypeCode"),
            "session_id": session_id,
        }

    def _extract_narratives(self, doc, ticker, session_id):
        doc_id = doc._data.get("docID")
        max_retries = 3
        report = None

        for attempt in range(max_retries):
            # Check global rate limit
            edinet_rate_limit.check_and_wait()

            try:
                report = doc.parse()
                break  # Success
            except Exception as e:
                error_msg = str(e)
                # Check for rate limit in error message
                if "429" in error_msg or "Too Many Requests" in error_msg:
                    logger.warning(
                        f"Rate limited (429) while parsing {doc_id}. Triggering global backoff."
                    )
                    edinet_rate_limit.trigger_backoff(60.0)
                    continue

                if "ConversionSyntax" in error_msg:
                    logger.warning(f"Data quality issue (Decimal conversion) for {doc_id}: {e}")
                    return []

                if "not a ZIP file" in error_msg and attempt < max_retries - 1:
                    logger.warning(
                        f"EDINET returned non-ZIP for {doc_id} (Attempt {attempt + 1}/{max_retries}). "
                        f"Triggering global backoff and retrying..."
                    )
                    edinet_rate_limit.trigger_backoff(60.0)
                    continue

                if "not found" in error_msg.lower() or "404" in error_msg:
                    logger.warning(f"Narrative unavailable (404) for {doc_id}")
                else:
                    logger.error(f"Narrative extraction failed for {doc_id}: {e}")
                return []

        if not report or not hasattr(report, "text_blocks"):
            return []

        from src.datalake.service.ensemble_parser import normalize_section_name
        from src.datalake.service.markdown_converter import clean_html_to_markdown

        results = []
        for k, v in report.text_blocks.items():
            if v and len(str(v)) > 20:
                normalized_key = normalize_section_name(k)
                markdown_content = clean_html_to_markdown(str(v))
                if markdown_content:
                    results.append(
                        {
                            "doc_id": doc_id,
                            "section_name": normalized_key,
                            "content_md": markdown_content,
                            "session_id": session_id,
                        }
                    )
        return results

    def _extract_facts(self, doc, ticker, session_id, csv_bytes=None):
        try:
            data = doc._data
            if data.get("csvFlag") != "1":
                return []
            content = csv_bytes
            if content is None:
                content = get_csv_from_edinet(data.get("docID"), settings.EDINET_API_KEY)
            if content is None:
                return None

            csv_data = parse_edinet_csv(content)
            fiscal_year = self._derive_fiscal_year(csv_data, data)
            results = []

            for file_name, df in csv_data.items():
                if df is None or df.empty:
                    continue

                cols = df.columns.tolist()
                val_col_idx = 8 if len(cols) >= 9 else len(cols) - 1
                name_col_idx = 1 if len(cols) >= 2 else 0
                unit_col_idx = 7 if len(cols) >= 8 else None

                for _, row in df.iterrows():
                    raw_val = str(row[cols[val_col_idx]]).replace(",", "").strip()
                    if not raw_val or raw_val.lower() in ["nan", "", "none"]:
                        continue

                    try:
                        val = float(raw_val)
                        results.append(
                            {
                                "doc_id": data.get("docID"),
                                "item_name": str(row[cols[name_col_idx]]),
                                "item_value": val,
                                "unit": str(row[cols[unit_col_idx]])
                                if unit_col_idx is not None
                                else "pure",
                                "context_id": str(row[cols[2]]) if len(cols) >= 3 else file_name,
                                "fiscal_year": fiscal_year,
                                "fiscal_period": "FY",
                                "session_id": session_id,
                            }
                        )
                    except (ValueError, TypeError):
                        continue
            return results
        except Exception as e:
            logger.error(f"Fact extraction failed for {doc._data.get('docID')}: {e}")
            return []

    def _derive_fiscal_year(self, csv_data, data):
        # Extract fiscal year from internal metadata (DEI)
        for file_name, df in csv_data.items():
            if "jpdei" in file_name.lower() and not df.empty:
                # Column 0 is the Element ID, Column 8 is the Value
                matches = df[
                    df.iloc[:, 0].astype(str).str.contains("CurrentFiscalYearEndDateDEI", na=False)
                ]
                if not matches.empty:
                    val = str(matches.iloc[0, 8])
                    try:
                        return pd.to_datetime(val).year
                    except Exception as e:
                        logger.debug(f"Failed to parse fiscal year date '{val}': {e}")
                        continue
        # Fallback
        filed_date = pd.to_datetime(data.get("submitDateTime")).date()
        return filed_date.year
