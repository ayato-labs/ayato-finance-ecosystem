import concurrent.futures
import json
import re
import zipfile

import pandas as pd
import zstandard as zstd
from edgar import Company, set_identity
from loguru import logger

from src.core.config import settings
from src.core.contracts import USFactContract, USNarrativeContract
from src.core.db import db_manager
from src.core.telemetry import trace_step
from src.core.utils import download_file, get_all_tickers, rate_limiter

def parse_company_facts_json(filename, content_str, ticker_map, session_id):
    """
    Parses a single company facts JSON string.
    """
    try:
        data = json.loads(content_str)
        cik_str = str(data.get("cik", "")).zfill(10)
        ticker = ticker_map.get(cik_str)
        if not ticker:
            return []

        facts = data.get("facts", {})
        if not facts:
            return []

        all_records = []
        for taxonomy, concepts in facts.items():
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

                        all_records.append(
                            (
                                ticker,
                                cik_str,
                                accn,
                                entry.get("form") or "UNKNOWN",
                                filed_date,
                                entry.get("fy"),
                                entry.get("fp") or "FY",
                                label,
                                float(entry.get("val", 0)) if entry.get("val") is not None else 0.0,
                                unit or "pure",
                                True,
                                concept,
                                session_id,
                            )
                        )
        return all_records
    except Exception as e:
        logger.error(f"Error parsing {filename}: {e}")
        return []

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
        from src.core.master_db import master_db
        from src.core.migrations import MigrationManager

        # 1. Migrate all databases independently
        MigrationManager.apply_migrations(self.facts_db)
        MigrationManager.apply_migrations(self.narratives_db)

        # 2. Register shards in Master DB
        master_db.register_shard("facts_db", str(self.facts_db), "facts", "v1.0.1")
        master_db.register_shard("narratives_db", str(self.narratives_db), "narratives", "v1.0.1")

    @trace_step(step_name="ingest_bulk_data")
    def ingest_bulk_data(self, session_id: str):
        """Processes all company facts from bulk ZIP with extreme diagnostic logging."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        zip_path = settings.DATA_DIR / "companyfacts.zip"
        
        # 1. Resource Check
        mem_mb = process.memory_info().rss / 1024 / 1024
        logger.info(f"DIAGNOSTIC: Ingestion starting. Current Memory: {mem_mb:.2f} MB")

        if not zip_path.exists():
            logger.error(f"ZIP not found at {zip_path}")
            return
        
        tickers = get_all_tickers()
        ticker_map = {t["cik"]: t["ticker"] for t in tickers}
        logger.info(f"Loaded {len(ticker_map)} tickers. Starting sequential scan...")

        with zipfile.ZipFile(zip_path, "r") as z:
            # We use infolist to check file sizes before reading
            all_files = [info for info in z.infolist() if info.filename.endswith(".json")]
            total_files = len(all_files)
            logger.info(f"Total JSON files in ZIP: {total_files}")

            batch_records = []
            relevant_count = 0
            
            for i, file_info in enumerate(all_files):
                filename = file_info.filename
                
                # Heartbeat and Memory check every 100 files
                if i % 100 == 0:
                    curr_mem = process.memory_info().rss / 1024 / 1024
                    logger.info(f"Progress: {i}/{total_files} | Memory: {curr_mem:.2f} MB | Relevant: {relevant_count}")

                try:
                    # PRE-READ DIAGNOSTIC
                    # Check for huge files (> 100MB uncompressed)
                    if file_info.file_size > 100 * 1024 * 1024:
                        logger.warning(f"Skipping potentially massive file: {filename} ({file_info.file_size / 1024 / 1024:.2f} MB)")
                        continue

                    # ACT: Read
                    content_bytes = z.read(filename)
                    content = content_bytes.decode("utf-8")
                    
                    # ACT: Parse
                    records = parse_company_facts_json(filename, content, ticker_map, session_id)
                    
                    if records:
                        batch_records.extend(records)
                        relevant_count += 1
                        
                        # Large Buffer Check: Save every 5000 facts
                        if len(batch_records) >= 5000:
                            logger.info(f"Buffer full ({len(batch_records)}). Triggering DB Save...")
                            self._save_raw_facts(batch_records)
                            batch_records = []
                            
                except Exception as e:
                    logger.error(f"Caught handled error in {filename}: {e}")
                    continue
                except BaseException as be:
                    logger.critical(f"UNHANDLED SYSTEM EXIT during {filename}: {type(be).__name__}")
                    raise

            # Final Cleanup
            if batch_records:
                logger.info(f"Saving final buffer of {len(batch_records)} facts.")
                self._save_raw_facts(batch_records)

        logger.info(f"Bulk ingestion completed. Scanned {total_files}, found {relevant_count} relevant companies.")

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
                        (ticker, cik, accession_number, form, filed_date, fiscal_year, fiscal_period, 
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

                contracts_to_save = []
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
                            ticker=ticker,
                            cik=str(filing.cik),
                            accession_number=filing.accession_no,
                            form=filing.form,
                            filed_date=filing.filing_date,
                            fiscal_year=period_date.year,
                            fiscal_period=f"Q{(period_date.month - 1) // 3 + 1}",
                            label=str(fact_label),
                            value=float(value),
                            unit="USD",
                            is_standardized=True,
                            raw_tag=str(raw_tag),
                            session_id=session_id,
                        )
                        contracts_to_save.append(contract)

                if contracts_to_save:
                    self._save_facts(contracts_to_save)

                logger.info(
                    f"Ingested statement for {ticker} ({filing.filing_date}) - {len(contracts_to_save)} facts"
                )
            except Exception as e:
                logger.error(f"Failed to ingest a statement for {ticker}: {e}")

    @trace_step(step_name="save_facts")
    def _save_facts(self, contracts: list[USFactContract]):
        if not contracts:
            return

        values = [
            (
                c.ticker,
                c.cik,
                c.accession_number,
                c.form,
                c.filed_date,
                c.fiscal_year,
                c.fiscal_period,
                c.label,
                c.value,
                c.unit,
                c.is_standardized,
                c.raw_tag,
                c.session_id,
            )
            for c in contracts
        ]
        with db_manager.connect(self.facts_db) as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO company_facts 
                (ticker, cik, accession_number, form, filed_date, fiscal_year, fiscal_period, 
                 label, value, unit, is_standardized, raw_tag, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                values,
            )

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
                (ticker, cik, accession_number, form, filed_date, section_name, content_md_zstd, session_id)
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
