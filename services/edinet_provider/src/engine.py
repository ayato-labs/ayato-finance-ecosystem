import concurrent.futures
import datetime
import pandas as pd
from loguru import logger

import edinet_tools
from src.core.config import settings
from src.core.db import db_manager
from src.core.contracts import FilingMetadata, CompanyFact, NarrativeBlock
from src.core.tracing import with_context


class JPEDINETEngine:
    def __init__(self):
        if not settings.EDINET_API_KEY:
            logger.warning("EDINET_API_KEY is not set. API calls will fail.")

        edinet_tools.configure(api_key=settings.EDINET_API_KEY)
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        from src.core.migrations import MigrationManager
        MigrationManager.apply_migrations()

    def _vacuum_db(self):
        """Run VACUUM to reclaim disk space and defragment."""
        logger.info("Running DB VACUUM to reclaim storage space...")
        try:
            with db_manager.connect_master() as conn:
                conn.execute("VACUUM;") # Only main database vacuum is reliably supported across versions
            logger.info("VACUUM completed successfully.")
        except Exception as e:
            logger.error(f"Failed to execute VACUUM: {e}")

    def sync_market(self, days: int = 30, session_id: str = "market-sync", max_workers: int = 20):
        logger.info(f"🚀 Launching Ultra-Fast Mode: Syncing market for the last {days} days...")
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=days)

        all_docs = []
        current_date = start_date
        while current_date <= end_date:
            try:
                docs = edinet_tools.documents(date=current_date)
                if docs:
                    all_docs.extend(docs)
            except Exception as e:
                logger.error(f"❌ Failed to fetch list for {current_date}: {e}", exc_info=True)
            current_date += datetime.timedelta(days=1)

        if not all_docs:
            logger.info("No documents found.")
            return

        self._process_docs_concurrently(all_docs, session_id, max_workers)
        self._vacuum_db()

    def sync_company(self, ticker: str, days: int = 30, session_id: str = "manual", max_workers: int = 20):
        """Sync specific company's latest filings."""
        logger.info(f"🔍 Syncing JP Company {ticker} (Last {days} days)...")
        try:
            entity = edinet_tools.entity(ticker)
            docs = entity.documents(days=days)
            if not docs:
                logger.info(f"No documents found for {ticker}.")
                return
            self._process_docs_concurrently(docs, session_id, max_workers)
        except Exception as e:
            logger.error(f"❌ Failed to sync {ticker}: {e}", exc_info=True)
        self._vacuum_db()

    def _process_docs_concurrently(self, docs, session_id, max_workers):
        if not docs:
            return

        # Step 1: Query existing doc IDs using a READ-ONLY connection
        with db_manager.connect_master(read_only=True) as conn:
            try:
                existing_doc_ids = {
                    row[0] for row in conn.execute("SELECT doc_id FROM registry_db.filings").fetchall()
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
        batch_size = 50
        results_batch = []
        processed_count = 0

        # Step 2: Process documents in parallel (Network I/O) without holding DB locks
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_doc = {
                executor.submit(
                    with_context(self._process_single_doc), doc, doc._data.get("secCode", "0000"), session_id
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

                    # Step 3: Flush batches to DB using a short-lived WRITE connection
                    if len(results_batch) >= batch_size:
                        with db_manager.connect_master() as conn:
                            self._flush_results_to_db(conn, results_batch)
                        results_batch = []
                        logger.info(f"Progress: {processed_count}/{len(docs_to_process)}")
                except Exception as e:
                    logger.error(f"Critical error processing doc {doc_id}: {e}", exc_info=True)

            # Final flush
            if results_batch:
                with db_manager.connect_master() as conn:
                    self._flush_results_to_db(conn, results_batch)

    def backfill_missing_data(self, max_workers: int = 20):
        logger.info("Starting backfill for missing data...")
        
        # Step 1: Query missing records using a READ-ONLY connection
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
                    (c.doc_id IS NULL AND (f.form_code LIKE '030000%' OR f.form_code LIKE '043000%' OR f.form_code = '030001'))
            """
            missing = conn.execute(query).fetchall()

        if not missing:
            logger.info("No missing data identified for backfill.")
            return

        logger.info(f"Identified {len(missing)} documents requiring backfill.")

        # Group by date to minimize API calls (edinet_tools.documents(date=...))
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
                        # Map sc back
                        sc = next(sc for did, sc in items if did == doc._data.get("docID"))
                        docs_to_process.append((doc, sc))
            except Exception as e:
                logger.error(f"Failed to fetch documents for backfill on {d}: {e}")

        if not docs_to_process:
            logger.warning("Could not retrieve any document objects for backfill.")
            return

        batch_size = 50
        results_batch = []
        processed_count = 0

        # Step 2: Process documents in parallel without holding DB locks
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_info = {
                executor.submit(with_context(self._process_single_doc), d, sc, "backfill"): d
                for d, sc in docs_to_process
            }
            for future in concurrent.futures.as_completed(future_to_info):
                try:
                    result = future.result()
                    if result:
                        results_batch.append(result)
                        processed_count += 1
                    
                    # Step 3: Flush batches using a short-lived WRITE connection
                    if len(results_batch) >= batch_size:
                        with db_manager.connect_master() as conn:
                            self._flush_results_to_db(conn, results_batch)
                        results_batch = []
                        logger.info(f"Backfill Progress: {processed_count}/{len(docs_to_process)}")
                except Exception as e:
                    logger.error(f"Backfill processing error: {e}")

            # Final flush
            if results_batch:
                with db_manager.connect_master() as conn:
                    self._flush_results_to_db(conn, results_batch)
            
        logger.info(f"Backfill completed. Processed {processed_count} documents.")

    def _process_single_doc(self, doc, ticker, session_id):
        doc_id = doc._data.get("docID")
        try:
            facts = self._extract_facts(doc, ticker, session_id)
            if facts is None and doc._data.get("csvFlag") == "1":
                return None
            
            metadata = self._extract_metadata(doc, ticker, session_id)
            narratives = self._extract_narratives(doc, ticker, session_id)
            
            # Validate through contracts
            valid_meta = FilingMetadata(**metadata)
            valid_facts = [CompanyFact(**f) for f in facts or []]
            valid_narrs = [NarrativeBlock(**n) for n in narratives or []]
            
            return {
                "metadata": valid_meta.model_dump(),
                "narratives": [n.model_dump() for n in valid_narrs],
                "facts": [f.model_dump() for f in valid_facts]
            }
        except Exception as e:
            logger.error(f"Contract validation failed for {doc_id}: {e}")
            return None

    def _flush_results_to_db(self, conn, results):
        # 1. Metadata (registry_db)
        metadata_batch = [
            (
                r["metadata"]["doc_id"], r["metadata"]["edinet_code"], r["metadata"]["sec_code"],
                r["metadata"]["filer_name"], r["metadata"]["doc_description"],
                r["metadata"]["submit_datetime"], r["metadata"]["form_code"],
                r["metadata"]["doc_type_code"], r["metadata"]["session_id"]
            ) for r in results
        ]
        self._batch_insert_resilient(
            conn, 
            "INSERT OR IGNORE INTO registry_db.filings (doc_id, edinet_code, sec_code, filer_name, doc_description, submit_datetime, form_code, doc_type_code, session_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            metadata_batch
        )

        # 2. Narratives (narr_db)
        narrative_batch = []
        for r in results:
            for n in r["narratives"]:
                narrative_batch.append((n["doc_id"], n["section_name"], n["content_md"], n["session_id"]))
        
        if narrative_batch:
            self._batch_insert_resilient(
                conn,
                "INSERT OR REPLACE INTO narr_db.narratives (doc_id, section_name, content_md, session_id) VALUES (?, ?, ?, ?)",
                narrative_batch
            )

        # 3. Facts (facts_db)
        fact_batch = []
        for r in results:
            for f in r["facts"]:
                fact_batch.append((
                    f["doc_id"], f["item_name"], f["item_value"], f["unit"],
                    f["context_id"], f["fiscal_year"], f["fiscal_period"], f["session_id"]
                ))
        
        if fact_batch:
            self._batch_insert_resilient(
                conn,
                "INSERT OR REPLACE INTO facts_db.company_facts (doc_id, item_name, item_value, unit, context_id, fiscal_year, fiscal_period, session_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                fact_batch
            )

    def _batch_insert_resilient(self, conn, sql, batch):
        """
        Attempts a batch insert. If it fails, falls back to individual inserts 
        to isolate and log the specific problematic record.
        """
        try:
            conn.executemany(sql, batch)
        except Exception as batch_err:
            logger.warning(f"Batch insert failed, falling back to individual inserts: {batch_err}")
            for record in batch:
                try:
                    conn.execute(sql, record)
                except Exception as rec_err:
                    logger.error(f"Isolation failed for record {record[0] if record else 'unknown'}: {rec_err}")

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
                    "session_id": session_id
                }
                for k, v in report.text_blocks.items() if len(str(v)) > 20
            ]
        except Exception as e:
            logger.error(
                "Narrative extraction failed for {doc_id}: {error}",
                doc_id=doc._data.get("docID"),
                error=str(e),
                extra={"doc_id": doc._data.get("docID")}
            )
            return []

    def _extract_facts(self, doc, ticker, session_id):
        try:
            from src.core.csv_parser import get_csv_from_edinet, parse_edinet_csv
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
                if len(cols) < 9:
                    continue
                for _, row in df.iterrows():
                    if pd.notna(row[cols[8]]):
                        try:
                            val = float(str(row[cols[8]]).replace(",", ""))
                            results.append({
                                "doc_id": data.get("docID"),
                                "item_name": str(row[cols[1]]),
                                "item_value": val,
                                "unit": str(row[cols[7]]),
                                "context_id": str(file_name),
                                "fiscal_year": filed_date.year,
                                "fiscal_period": "FY",
                                "session_id": session_id
                            })
                        except (ValueError, TypeError) as e:
                            logger.error(
                                "Failed to process data record: {error}",
                                error=str(e),
                                extra={"session_id": session_id}
                            )
                            continue
            return results
        except Exception as e:
            logger.error(
                "Fact extraction failed: {error}",
                error=str(e),
                extra={"session_id": session_id}
            )
            return []
