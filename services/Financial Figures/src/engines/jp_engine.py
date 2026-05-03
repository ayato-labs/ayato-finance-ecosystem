import logging

import duckdb
import jquantsapi
import pandas as pd
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.core.config import settings


class JPEngine:
    JP_TICKER_LEN_WITH_ZERO = 5

    def __init__(self, api_key: str | None = None, refresh_token: str | None = None):
        """
        Initialize the J-Quants engine.
        Supports dependency injection for easier testing.
        """
        self.db_path = settings.DB_PATH_JP
        # If explicitly passed (even as None/empty), use that. Otherwise fallback to settings.
        self.api_key = api_key if api_key is not None else settings.JQUANTS_API_KEY
        self.refresh_token = (
            refresh_token if refresh_token is not None else settings.JQUANTS_REFRESH_TOKEN
        )

        if not jquantsapi:
            raise ImportError("jquants-api-client is not installed.")

        # Priority: V1 (Refresh Token) > V2 (API Key)
        # We treat empty string as None/False for the priority check
        if self.refresh_token and len(str(self.refresh_token).strip()) > 0:
            logger.info(
                f"Using J-Quants V1 Client (Refresh Token: {str(self.refresh_token)[:5]}...)"
            )
            self.cli = jquantsapi.Client(refresh_token=self.refresh_token)
        elif self.api_key and len(str(self.api_key).strip()) > 0:
            logger.info("Using J-Quants V2 Client (API Key)")
            self.cli = jquantsapi.ClientV2(api_key=self.api_key)
        else:
            raise ValueError(
                "No J-Quants credentials found. "
                "Please set JQUANTS_API_KEY (V2) or JQUANTS_REFRESH_TOKEN (V1)."
            )

        self._init_db()

    def _init_db(self):
        """Initialize the Japan market database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if settings.db_read_only:
            logger.info("Skipping JP DB initialization in READ_ONLY mode.")
            return

        with duckdb.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tickers (
                    code VARCHAR PRIMARY KEY,
                    name VARCHAR,
                    market_section VARCHAR,
                    sector VARCHAR,
                    last_session_id VARCHAR
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS company_facts (
                    fact_id VARCHAR PRIMARY KEY,
                    code VARCHAR,
                    disclosed_date DATE,
                    fiscal_year INTEGER,
                    fiscal_period VARCHAR,
                    taxonomy VARCHAR,
                    tag VARCHAR,
                    label VARCHAR,
                    value DOUBLE,
                    unit VARCHAR,
                    accession_number VARCHAR,
                    session_id VARCHAR,
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Indexes for performance
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jp_facts_lookup "
                "ON company_facts (code, tag, disclosed_date)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jp_tickers_symbol ON tickers (code)")

    @retry(
        wait=wait_exponential(multiplier=2, min=4, max=60),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(Exception),  # jquantsapi might raise custom errors
        before_sleep=lambda retry_state: logger.warning(
            f"Retrying JP Ticker sync due to error: {retry_state.outcome.exception()}. "
            f"Attempt {retry_state.attempt_number}."
        ),
        reraise=True,
    )
    def sync_tickers(self, session_id: str | None = None) -> int:
        """Fetch listed company info using official client."""
        session_id = session_id or "manual-sync"
        logger.info("Syncing JP Ticker list from J-Quants API...")
        df = self.cli.get_list()

        if df.empty:
            return 0

        def get_col(df, options):
            for opt in options:
                if opt in df.columns:
                    return opt
            return None

        code_col = get_col(df, ["Code", "code", "LocalCode"])
        name_col = get_col(df, ["CoName", "CompanyName", "company_name", "name"])

        if not code_col or not name_col:
            raise KeyError(f"Could not find code or name columns. Columns: {df.columns.tolist()}")

        codes = df[code_col].astype(str).tolist()
        normalized_codes = [
            c[:4] if len(c) == self.JP_TICKER_LEN_WITH_ZERO and c.endswith("0") else c
            for c in codes
        ]

        df_mapped = pd.DataFrame(  # noqa: F841
            {
                "code": normalized_codes,
                "name": df[name_col],
                "market_section": df.get("MarketCodeName", df.get("Section", "")),
                "sector": df.get("Sector17CodeName", ""),
                "last_session_id": session_id,
            }
        )

        with duckdb.connect(str(self.db_path), read_only=settings.db_read_only) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tickers (
                    code, name, market_section, sector, last_session_id
                ) SELECT code, name, market_section, sector, last_session_id FROM df_mapped
                """
            )
            count = conn.execute("SELECT count(*) FROM tickers").fetchone()[0]
            logger.info(f"Successfully synced JP Tickers list. Total in DB: {count}")
            return count

    def fetch_statements(self, code: str) -> pd.DataFrame:
        """Fetch statements from J-Quants API, falling back to summary if details are restricted."""
        df = pd.DataFrame()
        try:
            if hasattr(self.cli, "get_fin_details"):
                df = self.cli.get_fin_details(code=code)
            else:
                df = self.cli.get_statements(code=code)
        except Exception as e:
            if any(err in str(e) for err in ["403", "400", "429"]):
                logger.info(
                    f"Fallback to summary for {code} due to API limit or restriction. (Error: {e})"
                )
                if hasattr(self.cli, "get_fin_summary"):
                    df = self.cli.get_fin_summary(code=code)
            else:
                raise e
        return df

    def fetch_and_ingest_statements(self, code: str, session_id: str):
        """Fetch and ingest statements (Legacy synchronous method)."""
        df = self.fetch_statements(code)
        if df is None or df.empty:
            logger.info(f"No statements found for JP Ticker {code}.")
            return
        logger.info(f"Fetched {len(df)} financial records for JP Ticker {code}.")
        self.ingest_facts(code, df, session_id)

    def ingest_facts(self, code: str, df: pd.DataFrame, session_id: str):
        """Flatten and ingest J-Quants statement data into DuckDB."""
        if df is None or df.empty:
            return

        all_records = []
        ignore_cols = [
            "LocalCode",
            "DisclosedDate",
            "FiscalYear",
            "FiscalPeriod",
            "DocType",
            "CurPerType",
            "CurPerSt",
            "CurPerEn",
            "CurFYSt",
            "CurFYEn",
            "NxtFYSt",
            "NxtFYEn",
            "DEPS",
            "REPS",
            "Type",
        ]
        date_options = ["DisclosedDate", "Date", "DiscDate"]
        date_col = next((c for c in date_options if c in df.columns), None)

        if not date_col:
            return

        for _, row in df.iterrows():
            disclosed_date = row.get(date_col)
            if hasattr(disclosed_date, "strftime"):
                disclosed_date = disclosed_date.strftime("%Y-%m-%d")

            fy = row.get("FiscalYear")
            fp = row.get("FiscalPeriod")
            ticker_code = str(row.get("LocalCode", row.get("Code", code)))
            if len(ticker_code) == self.JP_TICKER_LEN_WITH_ZERO and ticker_code.endswith("0"):
                ticker_code = ticker_code[:4]
            accn = f"{ticker_code}-{disclosed_date}"

            for col in df.columns:
                if col in ignore_cols or col == date_col:
                    continue

                val = row[col]
                # Silently skip empty values (empty string or whitespace)
                if isinstance(val, str) and val.strip() == "":
                    continue
                if pd.isna(val):
                    continue

                try:
                    val = float(val)
                except (ValueError, TypeError):
                    # Downgraded to DEBUG because J-Quants returns many non-numeric metadata columns
                    # (like DiscTime, Code, boolean flags) that are safely and expectedly skipped.
                    logger.debug(
                        f"Skipping non-numeric value for ticker {ticker_code}, "
                        f"column '{col}': {row[col]}."
                    )
                    continue
                except Exception as e:
                    logger.error(
                        f"Unexpected error parsing column '{col}' for {ticker_code}: {e}",
                        exc_info=True,
                    )
                    continue

                all_records.append(
                    {
                        "code": ticker_code,
                        "disclosed_date": disclosed_date,
                        "fiscal_year": fy,
                        "fiscal_period": fp,
                        "taxonomy": "JP-GAAP",
                        "tag": col,
                        "label": col,  # For JP, the raw column name is often the descriptive label
                        "value": val,
                        "unit": "JPY",
                        "accession_number": accn,
                        "session_id": session_id,
                    }
                )

        if not all_records:
            return

        logger.info(f"Ingesting {len(all_records)} fact records for JP Ticker {code}...")

        ingest_df = pd.DataFrame(all_records)  # noqa: F841
        with duckdb.connect(str(self.db_path), read_only=settings.db_read_only) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO company_facts (
                    fact_id, code, disclosed_date, fiscal_year, fiscal_period,
                    taxonomy, tag, label, value, unit, accession_number, session_id
                )
                SELECT
                    md5(concat_ws('|', code, disclosed_date, tag, accession_number)) as fact_id,
                    code, disclosed_date, fiscal_year, fiscal_period,
                    taxonomy, tag, label, value, unit, accession_number, session_id
                FROM ingest_df
                """
            )


if __name__ == "__main__":
    from dotenv import load_dotenv

    logging.basicConfig(level=logging.INFO)
    load_dotenv()
    engine = JPEngine()
    logger.info("JP Engine Initialized.")
