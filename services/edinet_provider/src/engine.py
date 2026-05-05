import concurrent.futures
import datetime
from pathlib import Path

import pandas as pd
from loguru import logger

import edinet_tools
from src.core.config import settings
from src.core.db import db_manager


class JPEDINETEngine:
    def __init__(self):
        if not settings.EDINET_API_KEY:
            logger.warning("EDINET_API_KEY is not set. API calls will fail.")

        # Configure the global client in edinet_tools
        edinet_tools.configure(api_key=settings.EDINET_API_KEY)

        self.db_path = settings.DB_PATH
        if str(self.db_path) != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _init_db(self):
        from src.core.migrations import MigrationManager

        MigrationManager.apply_migrations(self.db_path)

    def _vacuum_db(self):
        """Run VACUUM to reclaim disk space and defragment."""
        logger.info("Running DB VACUUM to reclaim storage space...")
        try:
            with db_manager.connect(self.db_path) as conn:
                conn.execute("VACUUM;")
            logger.info("VACUUM completed successfully.")
        except Exception as e:
            logger.error(f"Failed to execute VACUUM: {e}", exc_info=True)

    def sync_market(self, days: int = 30, session_id: str = "market-sync", max_workers: int = 20):
        """
        Ultra-Fast Mode: Prefetches metadata and processes all documents across dates in parallel.
        """
        logger.info(f"🚀 Launching Ultra-Fast Mode: Syncing market for the last {days} days...")
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=days)

        all_docs = []
        current_date = start_date
        logger.info(f"Phase 1/3: Gathering document lists from {start_date} to {end_date}...")

        while current_date <= end_date:
            try:
                # This API call is relatively lightweight (JSON list)
                docs = edinet_tools.documents(date=current_date)
                if docs:
                    all_docs.extend(docs)
                    logger.debug(f"Found {len(docs)} documents for {current_date}")
                else:
                    logger.debug(f"No documents found for {current_date}")
            except Exception as e:
                logger.error(f"❌ Failed to fetch list for {current_date}: {e}", exc_info=True)
            current_date += datetime.timedelta(days=1)

        if not all_docs:
            logger.info("No documents found for the specified period.")
            return

        logger.info(
            f"Phase 2/3: Starting parallel ingestion for {len(all_docs)} documents (Workers: {max_workers})..."
        )
        self._process_docs_concurrently(all_docs, session_id, max_workers)

        logger.info("Phase 3/3: Running maintenance...")
        self._vacuum_db()
        logger.info("✅ Market sync completed successfully.")

    def sync_company(
        self, ticker: str, days: int = 30, session_id: str = "manual", max_workers: int = 20
    ):
        """Sync specific company's latest filings."""
        logger.info(f"🔍 Syncing JP Company {ticker} (Last {days} days)...")
        try:
            entity = edinet_tools.entity(ticker)
            docs = entity.documents(days=days)
            if not docs:
                logger.info(f"No documents found for {ticker} in the last {days} days.")
                return
            logger.info(f"Found {len(docs)} documents for {ticker}. Processing...")
            self._process_docs_concurrently(docs, session_id, max_workers)
        except Exception as e:
            logger.error(f"❌ Failed to sync {ticker}: {e}", exc_info=True)

        self._vacuum_db()

    def _process_docs_concurrently(self, docs, session_id, max_workers):
        """Process a list of documents in parallel and save to DB."""
        if not docs:
            return

        with db_manager.connect(self.db_path) as conn:
            # Pre-fetch existing doc_ids to skip them efficiently
            logger.debug("Checking for existing documents in database...")
            try:
                existing_doc_ids = {
                    row[0] for row in conn.execute("SELECT doc_id FROM filings").fetchall()
                }
            except Exception as e:
                logger.error(f"Failed to query existing filings: {e}", exc_info=True)
                existing_doc_ids = set()

            docs_to_process = [
                doc for doc in docs if doc._data.get("docID") not in existing_doc_ids
            ]

            skipped_count = len(docs) - len(docs_to_process)
            if skipped_count > 0:
                logger.info(f"⏩ Skipped {skipped_count} already existing documents.")

            if not docs_to_process:
                logger.info("All documents are up-to-date.")
                return

            logger.info(f"🏗️ Processing {len(docs_to_process)} new documents...")

            batch_size = 50
            results_batch = []
            processed_count = 0

            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_doc = {
                    executor.submit(
                        self._process_single_doc, doc, doc._data.get("secCode", "0000"), session_id
                    ): doc
                    for doc in docs_to_process
                }

                for future in concurrent.futures.as_completed(future_to_doc):
                    doc = future_to_doc[future]
                    doc_id = doc._data.get("docID")
                    try:
                        result = future.result()
                        if result:
                            results_batch.append(result)
                            processed_count += 1

                        # Periodically flush batch to DB
                        if len(results_batch) >= batch_size:
                            logger.debug(f"Flushing batch of {len(results_batch)} results to DB...")
                            self._flush_results_to_db(conn, results_batch)
                            results_batch = []
                            logger.info(
                                f"📥 Progress: {processed_count}/{len(docs_to_process)} ingested (Last ID: {doc_id})"
                            )
                    except Exception as e:
                        logger.error(
                            f"💥 Critical error processing doc {doc_id}: {e}", exc_info=True
                        )

                # Final flush
                if results_batch:
                    try:
                        self._flush_results_to_db(conn, results_batch)
                        logger.info(
                            f"📥 Final batch of {len(results_batch)} documents ingested. Total: {processed_count}"
                        )
                    except Exception as e:
                        logger.error(f"❌ Failed to flush final batch: {e}", exc_info=True)

    def _process_single_doc(self, doc, ticker, session_id):
        """Extract all data for a single document. Executed in thread."""
        doc_id = doc._data.get("docID")
        logger.debug(f"Starting extraction for {doc_id} (ticker: {ticker})")

        try:
            metadata = self._extract_metadata(doc, ticker, session_id)
            narratives = self._extract_narratives(doc, ticker, session_id)
            facts = self._extract_facts(doc, ticker, session_id)

            logger.debug(f"Successfully extracted data for {doc_id}")
            return {"metadata": metadata, "narratives": narratives, "facts": facts}
        except Exception as e:
            logger.error(f"Failed extraction for {doc_id}: {e}", exc_info=True)
            return None

    def _flush_results_to_db(self, conn, results):
        """Atomically save a batch of results to the database."""
        try:
            # 1. Metadata (INSERT OR IGNORE)
            metadata_batch = [r["metadata"] for r in results]
            conn.executemany(
                """
                INSERT OR IGNORE INTO filings 
                (doc_id, edinet_code, sec_code, filer_name, doc_description, 
                 submit_datetime, form_code, doc_type_code, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                metadata_batch,
            )

            # 2. Narratives
            narrative_batch = []
            for r in results:
                narrative_batch.extend(r["narratives"])
            if narrative_batch:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO narratives 
                    (doc_id, section_name, content_md)
                    VALUES (?, ?, ?)
                """,
                    narrative_batch,
                )

            # 3. Facts
            fact_batch = []
            for r in results:
                fact_batch.extend(r["facts"])
            if fact_batch:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO company_facts 
                    (doc_id, item_name, item_value, unit, context_id, 
                     fiscal_year, fiscal_period)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    fact_batch,
                )
        except Exception as e:
            logger.error(f"Database batch insert failed: {e}", exc_info=True)
            raise  # Re-raise to trigger error handling in caller

    def _extract_metadata(self, doc, ticker, session_id):
        data = doc._data
        return [
            data.get("docID"),
            data.get("edinetCode"),
            ticker,
            data.get("filerName"),
            data.get("docDescription"),
            data.get("submitDateTime"),
            data.get("formCode"),
            data.get("docTypeCode"),
            session_id,
        ]

    def _extract_narratives(self, doc, ticker, session_id):
        try:
            data = doc._data
            if not data.get("formCode") or not data.get("formCode").startswith(("030000", "043")):
                return []

            report = doc.parse()
            if not report:
                return []

            biz = getattr(report, "business", None)
            sections = {
                "事業等のリスク": getattr(biz, "risks", None),
                "経営方針、経営環境及び対処すべき課題": getattr(
                    biz, "policy_environment_issue_etc", None
                ),
                "経営者による財政状態、経営成績及びキャッシュ・フローの状況の分析": getattr(
                    biz, "analysis_of_financial_results", None
                ),
            }

            results = []
            for name, content in sections.items():
                if content and len(str(content)) > 50:
                    results.append([data.get("docID"), name, str(content)])
            return results
        except Exception as e:
            logger.warning(f"Narrative extraction failed for {doc._data.get('docID')}: {e}")
            return []

    def _extract_facts(self, doc, ticker, session_id):
        try:
            from src.core.csv_parser import get_csv_from_edinet, parse_edinet_csv

            data = doc._data
            if data.get("csvFlag") != "1":
                return []

            content = get_csv_from_edinet(data.get("docID"), settings.EDINET_API_KEY)
            if not content:
                return []

            csv_data = parse_edinet_csv(content)
            filed_date = pd.to_datetime(data.get("submitDateTime")).date()

            results = []
            for file_name, df in csv_data.items():
                if df is None or df.empty:
                    continue

                cols = df.columns.tolist()
                if len(cols) < 9:
                    continue

                item_name_col = cols[1]
                unit_col = cols[7]
                value_col = cols[8]

                for _, row in df.iterrows():
                    item_name = row[item_name_col]
                    item_value = row[value_col]
                    unit = row[unit_col]

                    if pd.notna(item_value):
                        try:
                            str_val = str(item_value).replace(",", "")
                            val_float = float(str_val)
                            results.append(
                                [
                                    data.get("docID"),
                                    str(item_name),
                                    val_float,
                                    str(unit),
                                    str(file_name),
                                    filed_date.year,
                                    "FY",
                                ]
                            )
                        except (ValueError, TypeError):
                            continue
            return results
        except Exception as e:
            logger.warning(f"CSV fact extraction failed for {doc._data.get('docID')}: {e}")
            return []
