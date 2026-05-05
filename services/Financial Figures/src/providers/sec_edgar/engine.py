import threading
import time
from datetime import date
from typing import Any

import httpx
import pandas as pd
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.core.config import settings
from src.core.db import db_manager
from src.core.logging import track_performance


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
        """Initialize the US market database tables using MigrationManager."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if settings.db_read_only:
            logger.info("Skipping US DB initialization in READ_ONLY mode.")
            return

        from src.core.migrations import MigrationManager

        try:
            MigrationManager.apply_migrations(self.db_path, "us")
        except Exception as e:
            logger.error(f"Failed to initialize US database: {e}")
            raise

    @track_performance("sync_tickers_us")
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
        try:
            response = self.client.get(settings.SEC_TICKERS_URL)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"Failed to fetch ticker list from SEC: {e}")
            raise

        from src.core.contracts import USTickerContract

        # Convert to list of tuples for DuckDB insertion with validation
        records = []
        for key in data:
            item = data[key]
            # SEC CIKs in URLs must be 10 digits
            cik_str = str(item["cik_str"]).zfill(10)

            # Contract Validation
            try:
                contract = USTickerContract(
                    ticker=item["ticker"],
                    cik=cik_str,
                    name=item["title"],
                    last_session_id=session_id,
                )
                records.append(contract.model_dump())
            except Exception as e:
                logger.error(f"Ticker validation failed for {item.get('ticker')}: {e}")
                # We don't raise here to allow syncing other tickers, but we log the error

        if not records:
            logger.error("No valid tickers found in SEC response.")
            return 0

        df = pd.DataFrame(records)  # noqa: F841

        try:
            with db_manager.connect(self.db_path, read_only=settings.db_read_only) as conn:
                conn.execute(f"SET max_memory='{settings.DUCKDB_MEMORY_LIMIT}'")
                conn.execute(f"SET threads={settings.DUCKDB_THREADS}")
                conn.execute("PRAGMA disable_optimizer")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO tickers (ticker, cik, name, last_session_id)
                    SELECT ticker, cik, name, last_session_id FROM df
                    """
                )
                count = conn.execute("SELECT count(*) FROM tickers").fetchone()[0]
                logger.info(f"Successfully synced US Tickers list. Total in DB: {count}")
                return count
        except Exception as e:
            logger.error(f"Database error during US ticker sync: {e}")
            raise

    @track_performance("fetch_company_facts_us")
    @retry(
        wait=wait_exponential(multiplier=2, min=5, max=60),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        reraise=True,
    )
    def fetch_company_facts(self, ticker: str) -> dict[str, Any] | None:
        """Fetch fundamental data for a specific ticker from SEC CompanyFacts API."""
        try:
            with db_manager.connect(self.db_path, read_only=settings.db_read_only) as conn:
                conn.execute("PRAGMA disable_optimizer")
                res = conn.execute("SELECT cik FROM tickers WHERE ticker = ?", [ticker]).fetchone()
                if not res:
                    logger.warning(
                        f"Ticker {ticker} not found in local metadata. Syncing tickers first..."
                    )
                    self.sync_tickers()
                    res = conn.execute(
                        "SELECT cik FROM tickers WHERE ticker = ?", [ticker]
                    ).fetchone()

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
        except Exception as e:
            logger.error(f"Error fetching company facts for {ticker}: {e}")
            raise

    @track_performance("ingest_facts_us")
    def ingest_facts(self, ticker: str, facts_data: dict[str, Any], session_id: str):
        """Flatten and ingest SEC CompanyFacts JSON into DuckDB."""
        try:
            cik = str(facts_data.get("cik", "")).zfill(10)
            facts = facts_data.get("facts", {})

            from src.core.contracts import USFactContract

            all_records = []

            for taxonomy, tags in facts.items():
                for tag, details in tags.items():
                    units_dict = details.get("units", {})
                    label = details.get("label", tag)  # Store the descriptive label
                    for unit, data_points in units_dict.items():
                        for dp in data_points:
                            record = {
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

                            # Contract Validation
                            try:
                                contract = USFactContract(**record)
                                all_records.append(contract.model_dump())
                            except Exception as e:
                                # Log once per tag if it fails to avoid flooding
                                logger.error(f"Fact validation failed for {ticker} tag {tag}: {e}")
                                break

            if not all_records:
                logger.info(f"No valid fact records extracted for US Ticker {ticker}.")
                return

            logger.info(
                f"Extracted {len(all_records)} facts for US Ticker {ticker}. Ingesting to DB..."
            )

            df = pd.DataFrame(all_records)
            # Avoid Pandas nanosecond limit (year 2262) for DuckDB

            def safe_date_parse(x):
                try:
                    if not x or pd.isna(x):
                        return None
                    return date.fromisoformat(str(x))
                except Exception as e:
                    logger.warning(f"Failed to parse date '{x}': {e}")
                    return None

            df["end_date"] = df["end_date"].apply(safe_date_parse)
            df["filed_date"] = df["filed_date"].apply(safe_date_parse)

            with db_manager.connect(self.db_path, read_only=settings.db_read_only) as conn:
                conn.execute(f"SET max_memory='{settings.DUCKDB_MEMORY_LIMIT}'")
                conn.execute(f"SET threads={settings.DUCKDB_THREADS}")
                conn.execute("PRAGMA disable_optimizer")
                # Generate fact_id MD5 hash inside DuckDB for collision-free uniqueness
                conn.execute("""
                    INSERT OR IGNORE INTO company_facts (
                        fact_id, cik, taxonomy, tag, label, unit, value, end_date,
                        fiscal_year, fiscal_period, form, filed_date, accession_number, session_id
                    )
                    SELECT
                        md5(concat_ws('|', cik, taxonomy, tag, end_date, accession_number))
                          as fact_id,
                        cik, taxonomy, tag, label, unit, value, end_date,
                        fiscal_year, fiscal_period, form, filed_date, accession_number, session_id
                    FROM df
                """)
                logger.info(f"Successfully ingested facts for {ticker}.")
        except Exception as e:
            logger.error(f"Ingestion failed for US Ticker {ticker}: {e}")
            raise



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
