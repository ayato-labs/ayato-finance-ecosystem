import concurrent.futures
import gc
import json
import os
import queue
import re
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import psutil
import zstandard as zstd
from edgar import Company, set_identity
from loguru import logger

from edgar_core.config import settings
from edgar_core.contracts import USFactContract, USNarrativeContract, USFilingContract
from edgar_core.db import db_manager
from edgar_core.logging import track_performance
from edgar_core.telemetry import trace_step
from edgar_core.utils import get_all_tickers, rate_limiter


def parse_company_facts_json(filename, content_str, ticker_map, session_id):
    """
    Parses a single company facts JSON with strict range validation for DB safety.
    Returns (filings_records, fact_records).
    """
    try:
        data = json.loads(content_str)
        cik_str = str(data.get("cik", "")).zfill(10)
        ticker = ticker_map.get(cik_str)
        if not ticker:
            return [], []

        facts_data = data.get("facts", {})
        if not facts_data:
            return [], []

        filings_batch = {}  # accn -> filing_tuple
        fact_records = []

        for taxonomy, concepts in facts_data.items():
            for concept, concept_data in concepts.items():
                label = concept_data.get("label") or concept
                if not label:
                    continue

                units = concept_data.get("units", {})
                for unit, entries in units.items():
                    for entry in entries:
                        accn = entry.get("accn")
                        filed_date = entry.get("filed")
                        if not accn or not filed_date:
                            continue

                        # Register filing metadata if not seen in this file
                        if accn not in filings_batch:
                            filings_batch[accn] = (
                                accn,
                                ticker,
                                int(cik_str),
                                entry.get("form") or "UNKNOWN",
                                filed_date,
                                session_id,
                            )

                        # HARDENING: Clamp fiscal year to SMALLINT range
                        try:
                            fy = int(entry.get("fy", 0))
                            if not (1900 < fy < 2100):
                                fy = 0
                        except (ValueError, TypeError):
                            fy = 0

                        try:
                            val = (
                                float(entry.get("val", 0))
                                if entry.get("val") is not None
                                else 0.0
                            )
                            if pd.isna(val) or val == float("inf") or val == float("-inf"):
                                val = 0.0
                        except (ValueError, TypeError):
                            val = 0.0

                        fact_records.append(
                            (
                                accn,
                                fy,
                                entry.get("fp") or "FY",
                                label,
                                val,
                                unit or "pure",
                                True,
                                concept,
                            )
                        )
        return list(filings_batch.values()), fact_records
    except Exception as e:
        logger.error(f"Error parsing {filename}: {e}")
        return [], []


class USEngine:
    def __init__(self):
        set_identity(settings.SEC_IDENTITY)
        self.facts_db = settings.FACTS_DB_PATH
        self.narratives_db = settings.NARRATIVES_DB_PATH

        # Ensure directories exist
        self.facts_db.parent.mkdir(parents=True, exist_ok=True)
        self.narratives_db.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()
        self.compressor = zstd.ZstdCompressor(level=settings.ZSTD_COMPRESSION_LEVEL)

    def _init_db(self):
        from edgar_core.master_db import master_db
        from edgar_core.migrations import MigrationManager

        # 1. Migrate all databases independently
        MigrationManager.apply_migrations(self.facts_db, role="facts")
        MigrationManager.apply_migrations(self.narratives_db, role="narratives")

        # 2. Register shards in Master DB
        master_db.register_shard("facts_db", str(self.facts_db), "facts", "v1.1.0")
        master_db.register_shard("narratives_db", str(self.narratives_db), "narratives", "v1.1.0")

    @track_performance("ingest_bulk_data")
    @trace_step(step_name="ingest_bulk_data")
    def ingest_bulk_data(self, session_id: str):
        """Processes all company facts from bulk ZIP with extreme stability and speed."""
        process = psutil.Process(os.getpid())
        zip_path = settings.DATA_DIR / "companyfacts.zip"

        logger.info(f"INGEST START | Memory: {process.memory_info().rss / 1024 / 1024:.2f} MB")

        tickers = get_all_tickers()
        ticker_map = {t["cik"]: t["ticker"] for t in tickers}

        # Producer-Consumer Setup
        write_queue = queue.Queue(maxsize=20)  # Backpressure: limit pending batches
        stop_event = threading.Event()

        def db_writer_worker():
            """Dedicated thread for serial database writing."""
            with db_manager.connect(self.facts_db) as conn:
                # DuckDB specific bulk optimizations
                conn.execute("SET threads=1;")
                conn.execute(f"SET memory_limit='{settings.db_memory_limit}';")
                conn.execute("SET preserve_insertion_order=false;")
                
                # Drop secondary index during bulk ingestion
                logger.info("Dropping secondary index for bulk ingestion stability...")
                conn.execute("DROP INDEX IF EXISTS idx_us_facts_lookup;")
                conn.execute("DROP INDEX IF EXISTS idx_filings_ticker;")

                batch_count = 0
                while not stop_event.is_set() or not write_queue.empty():
                    try:
                        batch = write_queue.get(timeout=1)
                        if batch is None:
                            break
                        
                        filings, facts = batch
                        if filings or facts:
                            logger.info(f"Writing batch: {len(filings)} filings, {len(facts)} facts")
                            self._save_optimized(conn, filings, facts)
                            batch_count += 1
                            
                            # Periodic checkpoint to flush WAL and stabilize memory
                            if batch_count % 5 == 0:
                                logger.info("Periodic checkpoint...")
                                conn.execute("CHECKPOINT;")
                                
                            gc.collect()
                        
                        write_queue.task_done()
                    except queue.Empty:
                        continue
                    except Exception as e:
                        logger.error(f"Writer error: {e}")

                # Recreate index after bulk ingestion
                logger.info("Recreating secondary index...")
                conn.execute("CHECKPOINT;")
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_us_facts_lookup "
                    "ON company_facts (accession_number, fiscal_year, fiscal_period);"
                )
                conn.execute("CHECKPOINT;")
                logger.info("Writer thread finished.")

        # Start writer thread
        writer_thread = threading.Thread(target=db_writer_worker)
        writer_thread.start()

        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                all_files = [info for info in z.infolist() if info.filename.endswith(".json")]
                total_files = len(all_files)
                
                batch_filings = []
                batch_facts = []
                
                # Use ThreadPool for parallel parsing with a conservative worker count
                num_workers = min(os.cpu_count() or 4, 4)
                chunk_size = 1000  # Process files in chunks to avoid massive Future lists
                
                with ThreadPoolExecutor(max_workers=num_workers) as executor:
                    def process_file(file_info_name):
                        try:
                            with zipfile.ZipFile(zip_path, "r") as z_inner:
                                with z_inner.open(file_info_name) as f:
                                    content = f.read().decode("utf-8")
                            return parse_company_facts_json(
                                file_info_name, content, ticker_map, session_id
                            )
                        except Exception as e:
                            logger.error(f"Parse error {file_info_name}: {e}")
                            return [], []

                    for chunk_idx in range(0, total_files, chunk_size):
                        chunk = all_files[chunk_idx : chunk_idx + chunk_size]
                        futures = [executor.submit(process_file, info.filename) for info in chunk]
                        
                        for i, future in enumerate(concurrent.futures.as_completed(futures)):
                            current_total = chunk_idx + i
                            if current_total % 500 == 0:
                                mem = process.memory_info().rss / 1024 / 1024
                                logger.info(f"Progress: {current_total}/{total_files} | Mem: {mem:.2f}MB")

                            filing_recs, fact_recs = future.result()
                            
                            if filing_recs:
                                batch_filings.extend(filing_recs)
                                batch_facts.extend(fact_recs)

                                # Reduced batch size for RAM stability (100k -> 50k)
                                if len(batch_facts) >= 50000:
                                    write_queue.put((batch_filings, batch_facts))
                                    batch_filings = []
                                    batch_facts = []
                        
                        # Explicitly clear futures and trigger GC after each chunk
                        del futures
                        gc.collect()

                    # Final batch
                    if batch_filings or batch_facts:
                        write_queue.put((batch_filings, batch_facts))
                        batch_filings = []
                        batch_facts = []

        finally:
            # Signal writer to stop
            stop_event.set()
            write_queue.put(None)
            writer_thread.join()

            # Re-create secondary indexes after bulk operation completes
            logger.info("Re-creating secondary indexes...")
            with db_manager.connect(self.facts_db) as conn:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_filings_ticker ON filings (ticker);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_us_facts_lookup ON company_facts (accession_number, fiscal_year, fiscal_period);")

        logger.info("Bulk ingestion completed successfully.")

    def _save_optimized(self, conn, batch_filings_list, batch_facts_list):
        """Saves normalized records using the most stable Arrow-based approach."""
        if not batch_filings_list and not batch_facts_list:
            return

        try:
            # 1. Save filings
            if batch_filings_list:
                f_df = pd.DataFrame(
                    batch_filings_list,
                    columns=[
                        "accession_number",
                        "ticker",
                        "cik",
                        "form",
                        "filed_date",
                        "session_id",
                    ],
                )
                f_df.drop_duplicates(subset=["accession_number"], keep="last", inplace=True)
                f_df["filed_date"] = pd.to_datetime(f_df["filed_date"], errors="coerce").dt.date
                
                temp_parquet_path = settings.DATA_DIR / "temp" / f"tmp_f_{threading.get_ident()}.parquet"
                f_df.to_parquet(temp_parquet_path, engine="pyarrow")
                
                logger.debug("Executing INSERT OR REPLACE for filings")
                conn.execute(f"""
                    INSERT OR REPLACE INTO filings 
                    (accession_number, ticker, cik, form, filed_date, session_id)
                    SELECT * FROM read_parquet('{str(temp_parquet_path)}')
                """)
                
                if temp_parquet_path.exists():
                    temp_parquet_path.unlink()
                logger.debug("Filings insertion complete")

            # 2. Save facts
            if batch_facts_list:
                logger.debug("Creating facts DataFrame")
                df = pd.DataFrame(
                    batch_facts_list,
                    columns=[
                        "accession_number",
                        "fiscal_year",
                        "fiscal_period",
                        "label",
                        "value",
                        "unit",
                        "is_standardized",
                        "raw_tag",
                    ],
                )
                logger.debug("Dropping duplicates in facts")
                df.drop_duplicates(subset=["accession_number", "label"], keep="last", inplace=True)
                logger.debug("Converting value to numeric")
                df["value"] = pd.to_numeric(df["value"], errors="coerce").fillna(0.0)

                # Reduced sub-batch size for RAM stability (100k -> 50k)
                sub_batch_size = 50000
                logger.debug(f"Starting chunked insert for {len(df)} facts")
                for i in range(0, len(df), sub_batch_size):
                    logger.debug(f"Processing chunk {i}")
                    chunk_df = df.iloc[i : i + sub_batch_size]
                    
                    temp_parquet_path = settings.DATA_DIR / "temp" / f"tmp_c_{threading.get_ident()}.parquet"
                    chunk_df.to_parquet(temp_parquet_path, engine="pyarrow")
                    
                    conn.execute(f"""
                        INSERT OR REPLACE INTO company_facts 
                        (accession_number, fiscal_year, fiscal_period, label, value, unit, is_standardized, raw_tag)
                        SELECT * FROM read_parquet('{str(temp_parquet_path)}')
                    """)
                    
                    if temp_parquet_path.exists():
                        temp_parquet_path.unlink()
                logger.debug("Facts insertion complete")

        except Exception as e:
            logger.exception(f"Save failed during optimized batching: {e}")
            raise

    def _save_raw_facts(self, records: list[tuple]):
        """Saves raw record tuples to Facts DB in small sub-batches to prevent C-level crashes."""
        if not records:
            return

        clean_records = [
            r for r in records if r[0] is not None and r[2] is not None and r[7] is not None
        ]

        if not clean_records:
            return

        sub_batch_size = 1000
        total = len(clean_records)

        with db_manager.connect(self.facts_db) as conn:
            try:
                for start_idx in range(0, total, sub_batch_size):
                    end_idx = min(start_idx + sub_batch_size, total)
                    sub_records = clean_records[start_idx:end_idx]

                    conn.executemany(
                        """
                        INSERT OR REPLACE INTO company_facts
                        (ticker, cik, accession_number, form, filed_date,
                         fiscal_year, fiscal_period,
                         label, value, unit, is_standardized, raw_tag, session_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        sub_records,
                    )

                # Force commit to disk to free up DuckDB's internal memory
                conn.execute("CHECKPOINT;")
            except Exception as e:
                logger.error(f"Failed to save sub-batch to Facts DB: {e}")
                raise

    @track_performance("ingest_all_companies")
    @trace_step(step_name="ingest_all_companies")
    def ingest_all_companies(self, session_id: str):
        """Processes all companies with resume logic and rate limiting in parallel."""
        tickers = get_all_tickers()
        logger.info(f"Starting parallel ingestion for {len(tickers)} companies.")

        max_workers = settings.DUCKDB_THREADS * 2

        def process_single_company(item):
            ticker = item["ticker"]
            cik = item["cik"]

            # Check if already processed (Check Facts DB)
            with db_manager.connect(self.facts_db) as conn:
                res = conn.execute(
                    "SELECT status FROM processed_companies WHERE ticker = ?", [ticker]
                ).fetchone()
                if res and res[0] == "completed":
                    return

            try:
                self.fetch_and_ingest_company(ticker, session_id)
                self._update_processed_status(ticker, cik, "completed")
            except Exception as e:
                logger.error(f"Failed to ingest {ticker}: {e}")
                self._update_processed_status(ticker, cik, "failed", str(e))

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            executor.map(process_single_company, tickers)

        with db_manager.connect(self.facts_db) as conn:
            conn.execute("CHECKPOINT;")
        with db_manager.connect(self.narratives_db) as conn:
            conn.execute("CHECKPOINT;")

    def _update_processed_status(self, ticker, cik, status, error_log=None):
        with db_manager.connect(self.facts_db) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO processed_companies
                (ticker, cik, status, last_processed_at, error_log)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
            """,
                [ticker, cik, status, error_log],
            )

    @track_performance("fetch_and_ingest_company")
    @trace_step(step_name="fetch_and_ingest_company")
    def fetch_and_ingest_company(
        self, ticker: str, session_id: str, forms=["10-K", "10-Q"], limit=5
    ):
        """Fetch financials and narratives for a specific company."""
        logger.info(f"Processing {ticker}...")
        try:
            rate_limiter.wait()
            company = Company(ticker)

            rate_limiter.wait()
            filings = company.get_filings(form=forms).head(limit)

            for filing in filings:
                self._ingest_narratives(ticker, filing, session_id)

                try:
                    rate_limiter.wait()
                    xbrl = filing.xbrl()
                    if xbrl:
                        from edgar.financials import Financials

                        fin = Financials(xbrl)
                        self._ingest_financials(ticker, filing, fin, session_id)
                except Exception as e:
                    logger.warning(f"Financials not available for {filing}: {e}")

        except Exception as e:
            logger.error(f"Failed to process {ticker}: {e}")

    @trace_step(step_name="ingest_financials")
    def _ingest_financials(self, ticker, filing, financials, session_id):
        """Extracts standardized concepts from financial statements."""
        statement_methods = [
            financials.income_statement,
            financials.balance_sheet,
            financials.cash_flow_statement,
        ]

        for method in statement_methods:
            try:
                rate_limiter.wait()
                stmt = method()
                if stmt is None:
                    continue
                df = stmt.to_dataframe()
                if df is None or df.empty:
                    continue

                date_cols = []
                for col in df.columns:
                    try:
                        pd.to_datetime(col)
                        date_cols.append(col)
                    except (ValueError, TypeError):
                        continue

                filings_to_save = []
                contracts_to_save = []
                
                # We only need one filing record per filing
                filings_to_save.append(
                    USFilingContract(
                        accession_number=filing.accession_no,
                        ticker=ticker,
                        cik=str(filing.cik),
                        form=filing.form,
                        filed_date=filing.filing_date,
                        session_id=session_id,
                    )
                )

                for period_col in date_cols:
                    try:
                        period_date = pd.to_datetime(period_col).date()
                    except Exception:
                        continue

                    for _, row in df.iterrows():
                        value = row[period_col]
                        if pd.isna(value) or not isinstance(value, (int, float, complex)):
                            continue

                        fact_label = (
                            row.get("standard_concept") or row.get("label") or row.get("concept")
                        )
                        raw_tag = row.get("concept")

                        contract = USFactContract(
                            accession_number=filing.accession_no,
                            fiscal_year=period_date.year,
                            fiscal_period=f"Q{(period_date.month - 1) // 3 + 1}",
                            label=str(fact_label),
                            value=float(value),
                            unit="USD",
                            is_standardized=True,
                            raw_tag=str(raw_tag),
                        )
                        contracts_to_save.append(contract)

                if contracts_to_save:
                    self._save_facts(filings_to_save, contracts_to_save)

                logger.info(
                    f"Ingested statement for {ticker} ({filing.filing_date}) "
                    f"- {len(contracts_to_save)} facts"
                )
            except Exception as e:
                logger.error(f"Failed to ingest a statement for {ticker}: {e}")

    @trace_step(step_name="save_facts")
    def _save_facts(self, filings: list[USFilingContract], facts: list[USFactContract]):
        """Saves facts and their associated filings to the normalized database."""
        if not facts:
            return

        filing_values = [
            (
                f.accession_number,
                f.ticker,
                int(f.cik),
                f.form,
                f.filed_date,
                f.session_id,
            )
            for f in filings
        ]
        
        fact_values = [
            (
                c.accession_number,
                c.fiscal_year,
                c.fiscal_period,
                c.label,
                c.value,
                c.unit,
                c.is_standardized,
                c.raw_tag,
            )
            for c in facts
        ]

        with db_manager.connect(self.facts_db) as conn:
            # 1. Save filings
            if filing_values:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO filings
                    (accession_number, ticker, cik, form, filed_date, session_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    filing_values,
                )
            
            # 2. Save facts
            conn.executemany(
                """
                INSERT OR REPLACE INTO company_facts
                (accession_number, fiscal_year, fiscal_period, label, value, unit,
                 is_standardized, raw_tag)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                fact_values,
            )
            conn.execute("CHECKPOINT;")

    @trace_step(step_name="ingest_narratives")
    def _ingest_narratives(self, ticker, filing, session_id):
        """Extracts key sections from markdown content and saves to Narratives DB."""
        try:
            rate_limiter.wait()
            md = filing.markdown()
            if not md:
                return

            sections_config = [
                {"name": "Risk Factors", "patterns": [r"##\s+Item\s+1A\.?\s+Risk\s+Factors"]},
                {
                    "name": "MD&A",
                    "patterns": [
                        r"##\s+Item\s+7\.?\s+Management",
                        r"##\s+Item\s+2\.?\s+Management",
                    ],
                },
            ]

            for config in sections_config:
                content = self._extract_section(md, config["patterns"])
                if content:
                    compressed = self.compressor.compress(content.encode("utf-8"))
                    contract = USNarrativeContract(
                        ticker=ticker,
                        cik=str(filing.cik),
                        accession_number=filing.accession_no,
                        form=filing.form,
                        filed_date=filing.filing_date,
                        section_name=config["name"],
                        content_md_zstd=compressed,
                        session_id=session_id,
                    )
                    self._save_narrative(contract)
                    logger.info(f"Saved {config['name']} for {ticker} to Narratives DB")

        except Exception as e:
            logger.error(f"Narrative extraction failed for {filing}: {e}")

    def _extract_section(self, md: str, start_patterns: list[str]) -> str | None:
        """Heuristic to extract a section from markdown."""
        for pattern in start_patterns:
            match = re.search(pattern, md, re.IGNORECASE)
            if match:
                start_idx = match.start()
                next_match = re.search(r"\n##\s+Item\s+", md[match.end() :], re.IGNORECASE)
                if next_match:
                    end_idx = match.end() + next_match.start()
                    return md[start_idx:end_idx].strip()
                else:
                    return md[start_idx:].strip()
        return None

    def _save_narrative(self, contract: USNarrativeContract):
        with db_manager.connect(self.narratives_db) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO narratives
                (ticker, cik, accession_number, form, filed_date,
                 section_name, content_md_zstd, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                [
                    contract.ticker,
                    contract.cik,
                    contract.accession_number,
                    contract.form,
                    contract.filed_date,
                    contract.section_name,
                    contract.content_md_zstd,
                    contract.session_id,
                ],
            )
