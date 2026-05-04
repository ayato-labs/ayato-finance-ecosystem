import logging

import pandas as pd

from src.core.config import settings
from src.core.db import db_manager

logger = logging.getLogger(__name__)


class EDINETMapper:
    """
    Handles mapping between Security Codes (Ticker) and EDINET Codes
    using the master CSV provided by FSA.
    """

    TICKER_LEN_WITH_CHECK_DIGIT = 5

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Ensure the mapping table exists in DuckDB."""

        if settings.db_read_only:
            logger.debug("Skipping EDINET Mapping DB initialization in READ_ONLY mode.")
            return
        with db_manager.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS edinet_tickers (
                    edinet_code VARCHAR PRIMARY KEY,
                    ticker VARCHAR,
                    company_name VARCHAR,
                    submitter_type VARCHAR,
                    industry VARCHAR,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_edinet_ticker ON edinet_tickers(ticker)")

    def load_csv(self, csv_path: str):
        """
        Load EdinetcodeDlInfo.csv and update the database.
        The CSV is expected to be CP932 (Shift-JIS) encoded.
        """

        logger.info(f"Loading EDINET code master from {csv_path}")
        try:
            # Skip the first row (header info) and use the second row as header
            df = pd.read_csv(csv_path, encoding="cp932", skiprows=1)

            required_cols = {
                "EDINETコード": "edinet_code",
                "証券コード": "ticker",
                "提出者名": "company_name",
                "提出者種別": "submitter_type",
                "業種": "industry",
            }

            # Use column names if they match, otherwise positional (fallback)
            rename_map = {}
            for jp_name, en_name in required_cols.items():
                if jp_name in df.columns:
                    rename_map[jp_name] = en_name

            if len(rename_map) < len(required_cols):
                logger.warning("Some Japanese column names not found, using positional mapping.")
                df = df.iloc[:, [0, 11, 6, 1, 10]]
                df.columns = ["edinet_code", "ticker", "company_name", "submitter_type", "industry"]
            else:
                df = df.rename(columns=rename_map)
                df = df[list(required_cols.values())]

            # Cleanup Ticker
            def clean_ticker(val):
                if pd.isna(val):
                    return None
                s = str(val).strip().split(".")[0]
                if len(s) == self.TICKER_LEN_WITH_CHECK_DIGIT and s.endswith("0"):
                    return s[:4]
                return s

            df["ticker"] = df["ticker"].apply(clean_ticker)

            # Filter: Only keep rows with a ticker
            listed_df = df[df["ticker"].notna()].copy()
            logger.info(f"Identified {len(listed_df)} listed companies in CSV.")

            # UPSERT into DuckDB
            with db_manager.connect(self.db_path, read_only=settings.db_read_only) as conn:
                # Use a temp table for upsert
                conn.execute("CREATE TEMP TABLE tmp_edinet AS SELECT * FROM listed_df")
                conn.execute("""
                    INSERT OR REPLACE INTO edinet_tickers
                    SELECT
                        edinet_code, ticker, company_name, submitter_type, industry,
                        CURRENT_TIMESTAMP
                    FROM tmp_edinet
                """)
                logger.info("Successfully updated edinet_tickers master table.")

        except Exception as e:
            logger.error(f"Failed to load EDINET CSV: {e}", exc_info=True)
            raise

    def get_ticker_to_edinet(self) -> dict[str, str]:
        """Return a mapping of Ticker -> EDINET Code."""

        with db_manager.connect(self.db_path, read_only=settings.db_read_only) as conn:
            res = conn.execute("SELECT ticker, edinet_code FROM edinet_tickers").fetchall()
            return {r[0]: r[1] for r in res}

    def get_all_target_edinet_codes(self) -> list[str]:
        """Return a list of all EDINET codes for listed companies."""

        with db_manager.connect(self.db_path, read_only=settings.db_read_only) as conn:
            res = conn.execute("SELECT edinet_code FROM edinet_tickers").fetchall()
            return [r[0] for r in res]
