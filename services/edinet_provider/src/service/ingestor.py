import concurrent.futures
import datetime
import gc
import logging

# Suppress edinet_tools LLM warning before it gets imported
logging.getLogger().setLevel(logging.ERROR)
import edinet_tools
import pandas as pd
from loguru import logger

from src.infra.config import settings
from src.domain.contracts import CompanyFact, FilingMetadata, NarrativeBlock
from src.infra.db import db_manager
from src.infra.tracing import with_context
from .csv_parser import get_csv_from_edinet, parse_edinet_csv
from .writer import DatabaseWriter


class DataIngestor:
    def __init__(self):
        if not settings.EDINET_API_KEY:
            logger.warning("EDINET_API_KEY is not set. API calls will fail.")
        edinet_tools.configure(api_key=settings.EDINET_API_KEY)
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.writer = DatabaseWriter()

    def process_docs_concurrently(self, docs, session_id, max_workers):
        if not docs:
            logger.info("No documents provided for processing.")
            return

        logger.debug(f"Querying existing filings from registry for {len(docs)} candidates...")
        with db_manager.connect_master(read_only=True) as conn:
            try:
                existing_doc_ids = {
                    row[0]
                    for row in conn.execute("SELECT doc_id FROM registry_db.filings").fetchall()
                }
                logger.debug(f"Found {len(existing_doc_ids)} existing filings in DB.")
            except Exception as e:
                logger.error(f"Failed to query existing filings: {e}", exc_info=True)
                raise  # Do not swallow registry query failures

        docs_to_process = [doc for doc in docs if doc._data.get("docID") not in existing_doc_ids]

        if not docs_to_process:
            logger.info("All documents are up-to-date. Skipping ingestion.")
            return

        logger.info(f"Processing {len(docs_to_process)} new documents (Session: {session_id})...")
        processed_count = 0

        # Start the background writer
        self.writer.start()

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_doc = {
                    executor.submit(
                        with_context(self._process_single_doc),
                        doc,
                        doc._data.get("secCode", "0000"),
                        session_id,
                    ): doc
                    for doc in docs_to_process
                }

                for future in concurrent.futures.as_completed(future_to_doc):
                    doc = future_to_doc[future]
                    doc_id = doc._data.get("docID")
                    try:
                        result, status_info = future.result()
                        if result:
                            # Queue for asynchronous writing
                            self.writer.put("ingest", result)
                            logger.debug(f"Queued {doc_id} for DB write.")
                        else:
                            logger.warning(f"Processing returned empty for {doc_id}: {status_info}")

                        # Queue log update
                        log_data = (
                            doc_id,
                            status_info["status"],
                            datetime.datetime.now(),
                            status_info.get("error"),
                        )
                        self.writer.put("log", log_data)

                        processed_count += 1
                        if processed_count % 10 == 0:
                            logger.info(
                                f"Progress: {processed_count}/{len(docs_to_process)} (Queued)"
                            )
                    except Exception as e:
                        logger.error(f"Critical error processing doc {doc_id}: {e}", exc_info=True)

        finally:
            # Wait for all writes to finish and stop the writer
            logger.info("Finishing ingestion. Waiting for DB Writer to flush remaining data...")
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
                    (n.doc_id IS NULL AND (f.form_code LIKE '030000%' OR f.form_code LIKE '043000%'))
                    OR
                    (c.doc_id IS NULL AND (f.form_code LIKE '030000%' OR f.form_code LIKE '043000%'
                     OR f.form_code = '030001'))
            """
            missing = conn.execute(query).fetchall()

        if not missing:
            logger.info("No missing data identified for backfill.")
            return

        logger.info(f"Identified {len(missing)} documents requiring backfill.")

        by_date = {}
        for did, sc, dt in missing:
            d = pd.to_datetime(dt).date()
            if d not in by_date:
                by_date[d] = []
            by_date[d].append((did, sc))

        docs_to_process = []
        for d, items in by_date.items():
            try:
                all_docs_on_date = edinet_tools.documents(date=d)
                target_ids = {did for did, sc in items}
                for doc in all_docs_on_date:
                    if doc._data.get("docID") in target_ids:
                        sc = next(sc for did, sc in items if did == doc._data.get("docID"))
                        docs_to_process.append((doc, sc))
            except Exception as e:
                logger.error(f"Failed to fetch documents for backfill on {d}: {e}")

        if not docs_to_process:
            logger.warning("Could not retrieve any document objects for backfill.")
            return

        processed_count = 0
        self.writer.start()

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_info = {
                    executor.submit(with_context(self._process_single_doc), d, sc, "backfill"): d
                    for d, sc in docs_to_process
                }
                for future in concurrent.futures.as_completed(future_to_info):
                    try:
                        result, _ = future.result()
                        if result:
                            self.writer.put("ingest", result)
                            processed_count += 1

                        if processed_count % 10 == 0:
                            logger.info(
                                f"Backfill Progress: {processed_count}/{len(docs_to_process)} (Queued)"
                            )
                    except Exception as e:
                        logger.error(f"Backfill processing error: {e}")
        finally:
            self.writer.stop()
            gc.collect()

        logger.info(f"Backfill completed. Processed {processed_count} documents.")

    def _process_single_doc(self, doc, ticker, session_id):
        doc_id = doc._data.get("docID")
        status_info = {"status": "SUCCESS", "error": None}
        try:
            facts = self._extract_facts(doc, ticker, session_id)
            if facts is None and doc._data.get("csvFlag") == "1":
                status_info = {"status": "PARTIAL_FAIL", "error": "CSV content returned None"}
                return None, status_info

            metadata = self._extract_metadata(doc, ticker, session_id)
            narratives = self._extract_narratives(doc, ticker, session_id)

            if not narratives and (doc._data.get("formCode") or "").startswith(
                ("030000", "043000")
            ):
                status_info["status"] = "PARTIAL_FAIL"
                status_info["error"] = "No narrative blocks extracted (possible 404 or empty)"

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
            logger.error(f"Contract validation failed for {doc_id}: {e}")
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
        try:
            report = doc.parse()
            if not report or not hasattr(report, "text_blocks"):
                return []
            return [
                {
                    "doc_id": doc._data.get("docID"),
                    "section_name": k,
                    "content_md": str(v),
                    "session_id": session_id,
                }
                for k, v in report.text_blocks.items()
                if len(str(v)) > 20
            ]
        except Exception as e:
            error_msg = str(e).lower()
            if "not found" in error_msg or "404" in error_msg:
                logger.warning(
                    "Narrative unavailable (404/Not Found) for {doc_id}: {error}",
                    doc_id=doc._data.get("docID"),
                    error=str(e),
                    extra={"doc_id": doc._data.get("docID")},
                )
            else:
                logger.error(
                    "Narrative extraction failed for {doc_id}: {error}",
                    doc_id=doc._data.get("docID"),
                    error=str(e),
                    extra={"doc_id": doc._data.get("docID")},
                )
            return []

    def _extract_facts(self, doc, ticker, session_id):
        try:
            data = doc._data
            if data.get("csvFlag") != "1":
                return []
            content = get_csv_from_edinet(data.get("docID"), settings.EDINET_API_KEY)
            if content is None:
                return None

            csv_data = parse_edinet_csv(content)
            filed_date = pd.to_datetime(data.get("submitDateTime")).date()
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
                                "fiscal_year": filed_date.year,
                                "fiscal_period": "FY",
                                "session_id": session_id,
                            }
                        )
                    except (ValueError, TypeError):
                        continue
            return results
        except Exception as e:
            logger.error(
                "Fact extraction failed for {doc_id}: {error}",
                doc_id=doc._data.get("docID"),
                error=str(e),
                extra={"session_id": session_id},
            )
            return []
