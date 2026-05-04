import json
import os
import duckdb
from loguru import logger

class FinancialNarrativeStorage:
    def __init__(self, db_path: str = "finance_narratives.duckdb"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with duckdb.connect(self.db_path) as conn:
            conn.execute("SET memory_limit = '2GB'")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS filings (
                    accession_number VARCHAR PRIMARY KEY,
                    ticker VARCHAR,
                    cik VARCHAR,
                    form VARCHAR,
                    filing_date DATE,
                    sections JSON,
                    metadata JSON,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS structured_data (
                    accession_number VARCHAR PRIMARY KEY,
                    ticker VARCHAR,
                    structured_facts JSON,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info(f"Initialized DuckDB at {self.db_path} with 2GB limit")

    def save_filing(self, metadata: dict, sections: dict):
        acc_no = metadata.get("accessionNumber")
        ticker = metadata.get("ticker", "UNKNOWN").upper()
        cik = metadata.get("cik")
        form = metadata.get("form")
        filing_date = metadata.get("filingDate")
        
        sections_json = json.dumps(sections)
        metadata_json = json.dumps(metadata)

        with duckdb.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO filings (
                    accession_number, ticker, cik, form, filing_date, sections, metadata, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (acc_no, ticker, cik, form, filing_date, sections_json, metadata_json),
            )
            logger.success(f"Saved filing for {ticker} ({acc_no}) to DuckDB")

    def save_structuring(self, accession_number: str, ticker: str, structured_facts: dict):
        facts_json = json.dumps(structured_facts)
        with duckdb.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO structured_data (
                    accession_number, ticker, structured_facts, updated_at
                ) VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (accession_number, ticker.upper(), facts_json),
            )
            logger.success(f"Saved structured facts for {ticker} ({accession_number})")

    def get_structuring_by_ticker(self, ticker: str):
        with duckdb.connect(self.db_path) as conn:
            query = """
                SELECT structured_facts, updated_at
                FROM structured_data WHERE ticker = ? ORDER BY updated_at DESC
            """
            res = conn.execute(query, (ticker.upper(),)).fetchone()
            if res:
                return json.loads(res[0])
            return None

    def filing_exists(self, accession_number: str) -> bool:
        with duckdb.connect(self.db_path) as conn:
            res = conn.execute(
                "SELECT 1 FROM filings WHERE accession_number = ?", (accession_number,)
            ).fetchone()
            return res is not None

    def get_filings_by_ticker(self, ticker: str):
        with duckdb.connect(self.db_path) as conn:
            return conn.execute(
                "SELECT * FROM filings WHERE ticker = ? ORDER BY filing_date DESC",
                (ticker.upper(),),
            ).fetchall()

    def get_summary(self):
        with duckdb.connect(self.db_path) as conn:
            return conn.execute(
                "SELECT ticker, COUNT(*) as count FROM filings GROUP BY ticker"
            ).fetchall()
