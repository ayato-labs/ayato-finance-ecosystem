import threading
import time
from datetime import date
from typing import Any

import duckdb
import httpx
import pandas as pd
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.core.config import settings


class SECRateLimiter:
    """Thread-safe rate limiter for SEC EDGAR API (Limit: 10 requests per second)."""

    def __init__(self, requests_per_second: int = 10):
        self.delay = 1.0 / requests_per_second
        self.last_request_time = 0
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            elapsed = time.perf_counter() - self.last_request_time
            sleep_time = self.delay - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
            self.last_request_time = time.perf_counter()


# Global SEC rate limiter instance
sec_limiter = SECRateLimiter(10)


class USEngine:
    HTTP_NOT_FOUND = 404
    HTTP_TOO_MANY_REQUESTS = 429

    def __init__(self):
        self.db_path = settings.DB_PATH_US
        self._init_db()
        self.client = httpx.Client(headers={"User-Agent": settings.SEC_USER_AGENT})

    def _init_db(self):
        """Initialize the US market database tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if settings.db_read_only:
            logger.info("Skipping US DB initialization in READ_ONLY mode.")
            return

        with duckdb.connect(str(self.db_path)) as conn:
            # Table for Ticker to CIK mapping
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tickers (
                    ticker VARCHAR PRIMARY KEY,
                    cik VARCHAR,
                    name VARCHAR,
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_session_id VARCHAR
                )
            """)

            # Table for Financial Facts (Domain Data)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS company_facts (
                    fact_id VARCHAR PRIMARY KEY,
                    cik VARCHAR,
                    taxonomy VARCHAR,
                    tag VARCHAR,
                    label VARCHAR,
                    unit VARCHAR,
                    value DOUBLE,
                    end_date DATE,
                    fiscal_year INTEGER,
                    fiscal_period VARCHAR,
                    form VARCHAR,
                    filed_date DATE,
                    accession_number VARCHAR,
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    session_id VARCHAR
                )
            """)

            # Indexes for performance
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_us_facts_lookup "
                "ON company_facts (cik, tag, end_date)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_us_tickers_symbol ON tickers (ticker)")

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        reraise=True,
    )
    def sync_tickers(self, session_id: str | None = None) -> int:
        """Fetch and sync the ticker-to-CIK mapping from SEC."""
        session_id = session_id or "manual-sync"
        logger.info(f"Syncing US Ticker list from SEC ({settings.SEC_TICKERS_URL})...")
        response = self.client.get(settings.SEC_TICKERS_URL)
        response.raise_for_status()
        data = response.json()

        # Convert to list of tuples for DuckDB insertion
        records = []
        for key in data:
            item = data[key]
            # SEC CIKs in URLs must be 10 digits
            cik_str = str(item["cik_str"]).zfill(10)
            records.append((item["ticker"], cik_str, item["title"], session_id))

        df = pd.DataFrame(records, columns=["ticker", "cik", "name", "last_session_id"])  # noqa: F841

        with duckdb.connect(str(self.db_path), read_only=settings.db_read_only) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tickers (ticker, cik, name, last_session_id)
                SELECT ticker, cik, name, last_session_id FROM df
                """
            )
            count = conn.execute("SELECT count(*) FROM tickers").fetchone()[0]
            logger.info(f"Successfully synced US Tickers list. Total in DB: {count}")
            return count

    @retry(
        wait=wait_exponential(multiplier=2, min=5, max=60),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        reraise=True,
    )
    def fetch_company_facts(self, ticker: str) -> dict[str, Any] | None:
        """Fetch fundamental data for a specific ticker from SEC CompanyFacts API."""
        with duckdb.connect(str(self.db_path), read_only=settings.db_read_only) as conn:
            res = conn.execute("SELECT cik FROM tickers WHERE ticker = ?", [ticker]).fetchone()
            if not res:
                logger.warning(
                    f"Ticker {ticker} not found in local metadata. Syncing tickers first..."
                )
                self.sync_tickers()
                res = conn.execute("SELECT cik FROM tickers WHERE ticker = ?", [ticker]).fetchone()

            if not res:
                logger.error(f"Failed to resolve CIK for ticker {ticker} after re-sync.")
                return None

            cik = res[0]
            url = settings.SEC_COMPANY_FACTS_URL_BASE.format(cik=cik)

            logger.info(f"Fetching CompanyFacts for {ticker} (CIK: {cik}) from SEC API...")
            # Apply SEC Rate Limit
            sec_limiter.wait()
            response = self.client.get(url)

            if response.status_code == self.HTTP_NOT_FOUND:
                logger.warning(f"CIK {cik} ({ticker}) facts not found (404) at SEC.")
                return None

            if response.status_code == self.HTTP_TOO_MANY_REQUESTS:
                logger.warning(f"SEC Rate Limit Hit (429) for {ticker}. Backing off...")
                response.raise_for_status()

            response.raise_for_status()
            data = response.json()
            facts_count = len(data.get("facts", {}))
            logger.info(f"Successfully fetched {facts_count} taxonomies for {ticker}.")
            return data

    def ingest_facts(self, ticker: str, facts_data: dict[str, Any], session_id: str):
        """Flatten and ingest SEC CompanyFacts JSON into DuckDB."""
        cik = str(facts_data.get("cik", "")).zfill(10)
        facts = facts_data.get("facts", {})

        all_records = []

        for taxonomy, tags in facts.items():
            for tag, details in tags.items():
                units_dict = details.get("units", {})
                label = details.get("label", tag)  # Store the descriptive label
                for unit, data_points in units_dict.items():
                    for dp in data_points:
                        all_records.append(
                            {
                                "cik": cik,
                                "taxonomy": taxonomy,
                                "tag": tag,
                                "label": label,
                                "unit": unit,
                                "value": dp.get("val"),
                                "end_date": dp.get("end"),
                                "fiscal_year": dp.get("fy"),
                                "fiscal_period": dp.get("fp"),
                                "form": dp.get("form"),
                                "filed_date": dp.get("filed"),
                                "accession_number": dp.get("accn"),
                                "session_id": session_id,
                            }
                        )

        if not all_records:
            logger.info(f"No valid fact records extracted for US Ticker {ticker}.")
            return

        logger.info(
            f"Extracted {len(all_records)} fact records for US Ticker {ticker}. Ingesting to DB..."
        )

        df = pd.DataFrame(all_records)
        # Ensure correct date types for DuckDB without hitting Pandas nanosecond limit (year 2262)

        def safe_date_parse(x):
            try:
                if not x or pd.isna(x):
                    return None
                return date.fromisoformat(str(x))
            except Exception as e:
                logger.warning(f"Failed to parse date '{x}': {e}")
                return None

        logger.info(f"Ingesting {len(all_records)} fact records for US Ticker {ticker}...")
        df["end_date"] = df["end_date"].apply(safe_date_parse)
        df["filed_date"] = df["filed_date"].apply(safe_date_parse)

        with duckdb.connect(str(self.db_path), read_only=settings.db_read_only) as conn:
            # Generate fact_id MD5 hash inside DuckDB for collision-free uniqueness
            conn.execute("""
                INSERT OR IGNORE INTO company_facts (
                    fact_id, cik, taxonomy, tag, label, unit, value, end_date,
                    fiscal_year, fiscal_period, form, filed_date, accession_number, session_id
                )
                SELECT
                    md5(concat_ws('|', cik, taxonomy, tag, end_date, accession_number)) as fact_id,
                    cik, taxonomy, tag, label, unit, value, end_date,
                    fiscal_year, fiscal_period, form, filed_date, accession_number, session_id
                FROM df
            """)


if __name__ == "__main__":
    from src.core.config import settings

    engine = USEngine()
    logger.info("Syncing US Tickers...")
    count = engine.sync_tickers()
    logger.info(f"Total tickers synced: {count}")

    test_ticker = "AAPL"
    logger.info(f"Fetching facts for {test_ticker}...")
    data = engine.fetch_company_facts(test_ticker)
    if data:
        engine.ingest_facts(test_ticker, data, "test-session")
        logger.info(f"Ingested facts for {test_ticker}")
