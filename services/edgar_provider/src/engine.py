import pandas as pd
import zstandard as zstd
import re
import time
import json
import zipfile
import concurrent.futures
from loguru import logger
from edgar import set_identity, Company, get_filings
from src.core.config import settings
from src.core.db import db_manager
from src.core.contracts import USNarrativeContract, USFactContract
from src.core.utils import get_all_tickers, download_file, rate_limiter
from src.core.telemetry import trace_step

def parse_company_facts_json(cik, content_str, ticker_map, session_id):
    """
    Worker function to parse a single company facts JSON.
    Returns a list of tuples ready for executemany.
    """
    try:
        data = json.loads(content_str)
        cik_str = str(data.get("cik", "")).zfill(10)
        ticker = ticker_map.get(cik_str)
        if not ticker:
            # Not an error, just skipping companies we don't track
            return []

        facts = data.get("facts", {})
        if not facts:
            logger.debug(f"No facts found for {ticker} (CIK: {cik_str})")
            return []

        all_records = []
        
        for taxonomy, concepts in facts.items():
            for concept, concept_data in concepts.items():
                # Ensure label is not None and fall back to concept tag
                label = concept_data.get("label") or concept
                if not label:
                    continue
                    
                units = concept_data.get("units", {})
                for unit, entries in units.items():
                    for entry in entries:
                        # Primary Key fields (ticker, accession_number, label) must be NOT NULL
                        accn = entry.get("accn")
                        if not accn or not ticker:
                            continue
                            
                        # Mandatory fields for our schema logic
                        filed_date = entry.get("filed")
                        if not filed_date:
                            continue

                        # Map to our schema
                        record = (
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
                            True, # is_standardized
                            concept, # raw_tag
                            session_id
                        )
                        all_records.append(record)
        return all_records
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON for {cik}: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error parsing facts for {cik}: {e}")
        return []

class USEngine:
    def __init__(self):
        set_identity(settings.SEC_IDENTITY)
        self.db_path = settings.DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.compressor = zstd.ZstdCompressor(level=settings.ZSTD_COMPRESSION_LEVEL)

    def _init_db(self):
        from src.core.migrations import MigrationManager
        MigrationManager.apply_migrations(self.db_path)

    @trace_step(step_name="ingest_bulk_data")
    def ingest_bulk_data(self, session_id: str):
        """Processes all company facts from the bulk ZIP file."""
        bulk_zip_url = "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip"
        zip_path = settings.DATA_DIR / "companyfacts.zip"
        
        # 1. Download if not exists
        if not zip_path.exists():
            if not download_file(bulk_zip_url, zip_path):
                logger.error("Failed to download bulk data.")
                return
        else:
            logger.info(f"Bulk data already exists at {zip_path}. Skipping download.")

        # 2. Get CIK-Ticker map
        tickers = get_all_tickers()
        ticker_map = {t["cik"]: t["ticker"] for t in tickers}
        logger.info(f"Loaded {len(ticker_map)} tickers for mapping.")

        # 3. Process ZIP in parallel
        logger.info("Starting parallel processing of bulk ZIP...")
        all_facts = []
        batch_size = 500 # Number of companies to process before committing to DB
        
        with zipfile.ZipFile(zip_path, 'r') as z:
            file_list = [name for name in z.namelist() if name.endswith('.json')]
            logger.info(f"Total files in ZIP: {len(file_list)}")
            
            # Using ProcessPoolExecutor for CPU-bound JSON parsing
            with concurrent.futures.ProcessPoolExecutor(max_workers=settings.DUCKDB_THREADS) as executor:
                # We process in batches to manage memory
                for i in range(0, len(file_list), batch_size):
                    chunk = file_list[i : i + batch_size]
                    futures = []
                    for filename in chunk:
                        with z.open(filename) as f:
                            content = f.read().decode('utf-8')
                            futures.append(executor.submit(parse_company_facts_json, filename, content, ticker_map, session_id))
                    
                    # Collect results from this batch
                    batch_facts = []
                    for future in concurrent.futures.as_completed(futures):
                        batch_facts.extend(future.result())
                    
                    if batch_facts:
                        self._save_raw_facts(batch_facts)
                        logger.info(f"Processed batch {i//batch_size + 1}: saved {len(batch_facts)} facts.")
        
        logger.info("Bulk ingestion completed.")

    def _save_raw_facts(self, records: list[tuple]):
        """Saves raw record tuples to DB."""
        if not records:
            return

        # Defensive filter: Primary Key components (ticker, accession_number, label) must NOT be NULL
        # ticker: r[0], accession_number: r[2], label: r[7]
        clean_records = [
            r for r in records 
            if r[0] is not None and r[2] is not None and r[7] is not None
        ]
        
        discarded_count = len(records) - len(clean_records)
        if discarded_count > 0:
            logger.warning(f"Discarded {discarded_count} records due to NULL values in Primary Key columns.")

        if not clean_records:
            return

        with db_manager.connect(self.db_path) as conn:
            try:
                conn.executemany("""
                    INSERT OR REPLACE INTO company_facts 
                    (ticker, cik, accession_number, form, filed_date, fiscal_year, fiscal_period, 
                     label, value, unit, is_standardized, raw_tag, session_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, clean_records)
            except Exception as e:
                logger.error(f"Failed to save batch: {e}")
                # Log the first record for debugging if it failed despite cleaning
                if clean_records:
                    logger.debug(f"Sample record: {clean_records[0]}")
                raise

    @trace_step(step_name="ingest_all_companies")
    def ingest_all_companies(self, session_id: str):
        """Processes all companies with resume logic and rate limiting in parallel."""
        tickers = get_all_tickers()
        logger.info(f"Starting parallel ingestion for {len(tickers)} companies.")
        
        # To avoid over-threading the API, we use a controlled number of workers.
        # Even with many threads, the RateLimiter ensures we don't exceed 9 req/s.
        max_workers = settings.DUCKDB_THREADS * 2 
        
        def process_single_company(item):
            ticker = item["ticker"]
            cik = item["cik"]
            
            # Check if already processed
            with db_manager.connect(self.db_path) as conn:
                res = conn.execute("SELECT status FROM processed_companies WHERE ticker = ?", [ticker]).fetchone()
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

        with db_manager.connect(self.db_path) as conn:
            logger.info("Executing CHECKPOINT to consolidate storage...")
            conn.execute("CHECKPOINT;")

    def _update_processed_status(self, ticker, cik, status, error_log=None):
        with db_manager.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO processed_companies 
                (ticker, cik, status, last_processed_at, error_log)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
            """, [ticker, cik, status, error_log])

    @trace_step(step_name="fetch_and_ingest_company")
    def fetch_and_ingest_company(self, ticker: str, session_id: str, forms=["10-K", "10-Q"], limit=5):
        """Fetch financials and narratives for a specific company."""
        logger.info(f"Processing {ticker}...")
        try:
            # 1. Fetch company (Initial API call)
            rate_limiter.wait()
            company = Company(ticker)
            
            # 2. Get filings (API call)
            rate_limiter.wait()
            filings = company.get_filings(form=forms).head(limit)
            
            for filing in filings:
                # 3. Ingest Narratives (MD&A and Risk Factors)
                # filing.markdown() and filing.xbr() will trigger API calls
                self._ingest_narratives(ticker, filing, session_id)
                
                # 4. Ingest Standardized Financials
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
        # Note: financials.income_statement() etc. might perform internal requests
        statement_methods = [
            financials.income_statement,
            financials.balance_sheet,
            financials.cash_flow_statement
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

                # Identify date columns
                date_cols = []
                for col in df.columns:
                    try:
                        # Attempt to parse column name as date
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

                        # Preferred label: standard_concept > label > concept
                        fact_label = row.get('standard_concept') or row.get('label') or row.get('concept')
                        raw_tag = row.get('concept')

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
                            session_id=session_id
                        )
                        contracts_to_save.append(contract)
                
                if contracts_to_save:
                    self._save_facts(contracts_to_save)
                    
                logger.info(f"Ingested statement for {ticker} ({filing.filing_date}) - {len(contracts_to_save)} facts")
            except Exception as e:
                logger.error(f"Failed to ingest a statement for {ticker}: {e}")

    @trace_step(step_name="save_facts")
    def _save_facts(self, contracts: list[USFactContract]):
        if not contracts:
            return
            
        values = [
            (
                c.ticker, c.cik, c.accession_number, c.form,
                c.filed_date, c.fiscal_year, c.fiscal_period,
                c.label, c.value, c.unit, c.is_standardized,
                c.raw_tag, c.session_id
            )
            for c in contracts
        ]
        with db_manager.connect(self.db_path) as conn:
            conn.executemany("""
                INSERT OR REPLACE INTO company_facts 
                (ticker, cik, accession_number, form, filed_date, fiscal_year, fiscal_period, 
                 label, value, unit, is_standardized, raw_tag, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, values)

    @trace_step(step_name="ingest_narratives")
    def _ingest_narratives(self, ticker, filing, session_id):
        """Extracts key sections from markdown content."""
        try:
            rate_limiter.wait()
            md = filing.markdown()
            if not md:
                logger.warning(f"No markdown content for {filing}")
                return

            sections_config = [
                {"name": "Risk Factors", "patterns": [r"##\s+Item\s+1A\.?\s+Risk\s+Factors"]},
                {"name": "MD&A", "patterns": [r"##\s+Item\s+7\.?\s+Management", r"##\s+Item\s+2\.?\s+Management"]}
            ]

            for config in sections_config:
                content = self._extract_section(md, config["patterns"])
                if content:
                    compressed = self.compressor.compress(content.encode('utf-8'))
                    contract = USNarrativeContract(
                        ticker=ticker,
                        cik=str(filing.cik),
                        accession_number=filing.accession_no,
                        form=filing.form,
                        filed_date=filing.filing_date,
                        section_name=config["name"],
                        content_md_zstd=compressed,
                        session_id=session_id
                    )
                    self._save_narrative(contract)
                    logger.info(f"Saved {config['name']} for {ticker} ({filing.filing_date})")

        except Exception as e:
            logger.error(f"Narrative extraction failed for {filing}: {e}")

    def _extract_section(self, md: str, start_patterns: list[str]) -> str | None:
        """Heuristic to extract a section from markdown until the next '## Item' header."""
        for pattern in start_patterns:
            match = re.search(pattern, md, re.IGNORECASE)
            if match:
                start_idx = match.start()
                next_match = re.search(r'\n##\s+Item\s+', md[match.end():], re.IGNORECASE)
                if next_match:
                    end_idx = match.end() + next_match.start()
                    return md[start_idx:end_idx].strip()
                else:
                    return md[start_idx:].strip()
        return None

    def _save_narrative(self, contract: USNarrativeContract):
        with db_manager.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO narratives 
                (ticker, cik, accession_number, form, filed_date, section_name, content_md_zstd, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                contract.ticker, contract.cik, contract.accession_number, 
                contract.form, contract.filed_date, contract.section_name, 
                contract.content_md_zstd, contract.session_id
            ])
