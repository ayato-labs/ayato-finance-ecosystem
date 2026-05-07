import concurrent.futures
import datetime
import gc

import edinet_tools
import pandas as pd
from loguru import logger

from src.infra.config import settings
from src.domain.contracts import CompanyFact, FilingMetadata, NarrativeBlock
from src.infra.db import db_manager
from src.infra.tracing import with_context
from .csv_parser import get_csv_from_edinet, parse_edinet_csv


class DataIngestor:
    def __init__(self):
        if not settings.EDINET_API_KEY:
            logger.warning("EDINET_API_KEY is not set. API calls will fail.")
        edinet_tools.configure(api_key=settings.EDINET_API_KEY)
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)

    def process_docs_concurrently(self, docs, session_id, max_workers):
        if not docs:
            return

        with db_manager.connect_master(read_only=True) as conn:
            try:
                existing_doc_ids = {
                    row[0]
                    for row in conn.execute("SELECT doc_id FROM registry_db.filings").fetchall()
                }
            except Exception as e:
                logger.error(f"Failed to query existing filings: {e}", exc_info=True)
                existing_doc_ids = set()

        docs_to_process = [
            doc for doc in docs if doc._data.get("docID") not in existing_doc_ids
        ]

        if not docs_to_process:
            logger.info("All documents are up-to-date.")
            return

        logger.info(f"Processing {len(docs_to_process)} new documents...")
        batch_size = 20
        results_batch = []
        log_batch = []
        processed_count = 0

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
                        results_batch.append(result)

                    log_batch.append(
                        (
                            doc_id,
                            status_info["status"],
                            datetime.datetime.now(),
                            status_info.get("error"),
                        )
                    )
                    processed_count += 1

                    if len(results_batch) >= batch_size or len(log_batch) >= batch_size:
                        with db_manager.connect_master() as conn:
                            if results_batch:
                                self._flush_results_to_db(conn, results_batch)
                                results_batch.clear()
                            if log_batch:
                                self._update_ingestion_logs(conn, log_batch)
                                log_batch.clear()
                        gc.collect()
                        logger.info(f"Progress: {processed_count}/{len(docs_to_process)}")
                except Exception as e:
                    logger.error(f"Critical error processing doc {doc_id}: {e}", exc_info=True)

            if results_batch or log_batch:
                with db_manager.connect_master() as conn:
                    if results_batch:
                        self._flush_results_to_db(conn, results_batch)
                    if log_batch:
                        self._update_ingestion_logs(conn, log_batch)
                results_batch.clear()
                log_batch.clear()
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
                # Use simple edinet_tools call for backfill to avoid cache dependency if needed,
                # but cache is generally better.
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

        batch_size = 20
        results_batch = []
        processed_count = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_info = {
                executor.submit(
                    with_context(self._process_single_doc), d, sc, "backfill"
                ): d
                for d, sc in docs_to_process
            }
            for future in concurrent.futures.as_completed(future_to_info):
                try:
                    result, _ = future.result()
                    if result:
                        results_batch.append(result)
                        processed_count += 1

                    if len(results_batch) >= batch_size:
                        with db_manager.connect_master() as conn:
                            self._flush_results_to_db(conn, results_batch)
                        results_batch.clear()
                        gc.collect()
                        logger.info(f"Backfill Progress: {processed_count}/{len(docs_to_process)}")
                except Exception as e:
                    logger.error(f"Backfill processing error: {e}")

            if results_batch:
                with db_manager.connect_master() as conn:
                    self._flush_results_to_db(conn, results_batch)
                results_batch.clear()
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

    def _flush_results_to_db(self, conn, results):
        metadata_batch = [
            (
                r["metadata"]["doc_id"],
                r["metadata"]["edinet_code"],
                r["metadata"]["sec_code"],
                r["metadata"]["filer_name"],
                r["metadata"]["doc_description"],
                r["metadata"]["submit_datetime"],
                r["metadata"]["form_code"],
                r["metadata"]["doc_type_code"],
                r["metadata"]["session_id"],
            )
            for r in results
        ]
        self._batch_insert_resilient(
            conn,
            "INSERT OR IGNORE INTO registry_db.filings (doc_id, edinet_code, sec_code, filer_name, "
            "doc_description, submit_datetime, form_code, doc_type_code, session_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            metadata_batch,
        )

        narrative_batch = [
            (n["doc_id"], n["section_name"], n["content_md"], n["session_id"])
            for r in results
            for n in r["narratives"]
        ]

        if narrative_batch:
            self._batch_insert_resilient(
                conn,
                "INSERT OR REPLACE INTO narr_db.narratives (doc_id, section_name, content_md, "
                "session_id) VALUES (?, ?, ?, ?)",
                narrative_batch,
            )

        fact_batch = [
            (
                f["doc_id"],
                f["item_name"],
                f["item_value"],
                f["unit"],
                f["context_id"],
                f["fiscal_year"],
                f["fiscal_period"],
                f["session_id"],
            )
            for r in results
            for f in r["facts"]
        ]

        if fact_batch:
            self._batch_insert_resilient(
                conn,
                "INSERT OR REPLACE INTO facts_db.company_facts (doc_id, item_name, item_value, "
                "unit, context_id, fiscal_year, fiscal_period, session_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                fact_batch,
            )

    def _batch_insert_resilient(self, conn, sql, batch):
        try:
            conn.executemany(sql, batch)
        except Exception as batch_err:
            logger.warning(f"Batch insert failed, falling back to individual inserts: {batch_err}")
            for record in batch:
                try:
                    conn.execute(sql, record)
                except Exception as rec_err:
                    logger.error(
                        f"Isolation failed for record {record[0] if record else 'unknown'}: {rec_err}"
                    )

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

    def _update_ingestion_logs(self, conn, logs):
        """Batch update ingestion_log table."""
        sql = """
            INSERT INTO ingestion_log (doc_id, status, last_attempt, error_message, retry_count)
            VALUES (?, ?, ?, ?, 0)
            ON CONFLICT (doc_id) DO UPDATE SET
                status = excluded.status,
                last_attempt = excluded.last_attempt,
                error_message = excluded.error_message,
                retry_count = retry_count + 1
        """
        conn.executemany(sql, logs)
