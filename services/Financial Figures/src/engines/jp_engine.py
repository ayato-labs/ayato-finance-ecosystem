import pandas as pd
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.core.config import settings
from src.core.db import db_manager
from src.core.logging import track_performance

try:
    import jquantsapi
except ImportError:
    jquantsapi = None

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
        """Initialize the Japan market database using MigrationManager."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if settings.db_read_only:
            logger.info("Skipping JP DB initialization in READ_ONLY mode.")
            return

        from src.core.migrations import MigrationManager

        try:
            MigrationManager.apply_migrations(self.db_path, "jp")
        except Exception as e:
            logger.error(f"Failed to initialize JP database: {e}")
            raise

    @track_performance("sync_tickers_jp")
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
        try:
            df = self.cli.get_list()
        except Exception as e:
            logger.error(f"Failed to fetch ticker list from J-Quants: {e}")
            raise

        if df.empty:
            logger.warning("J-Quants ticker list is empty.")
            return 0

        from src.core.contracts import JPTickerContract

        def get_col(df, options):
            for opt in options:
                if opt in df.columns:
                    return opt
            return None

        code_col = get_col(df, ["Code", "code", "LocalCode"])
        name_col = get_col(df, ["CoName", "CompanyName", "company_name", "name"])

        if not code_col or not name_col:
            err_msg = f"Could not find code or name columns. Columns: {df.columns.tolist()}"
            logger.error(err_msg)
            raise KeyError(err_msg)

        records = []
        for _, row in df.iterrows():
            code = str(row[code_col])
            # Normalize JP code (5 digits ending in 0 -> 4 digits)
            if len(code) == self.JP_TICKER_LEN_WITH_ZERO and code.endswith("0"):
                code = code[:4]

            try:
                contract = JPTickerContract(
                    code=code,
                    name=row[name_col],
                    market_section=row.get("MarketCodeName", row.get("Section", "")),
                    sector=row.get("Sector17CodeName", ""),
                    last_session_id=session_id,
                )
                records.append(contract.model_dump())
            except Exception as e:
                logger.error(f"JP Ticker validation failed for {code}: {e}")

        if not records:
            logger.error("No valid JP tickers found after validation.")
            return 0

        df_mapped = pd.DataFrame(records)  # noqa: F841

        try:
            with db_manager.connect(self.db_path, read_only=settings.db_read_only) as conn:
                conn.execute(f"SET max_memory='{settings.DUCKDB_MEMORY_LIMIT}'")
                conn.execute(f"SET threads={settings.DUCKDB_THREADS}")
                conn.execute("PRAGMA disable_optimizer")
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
        except Exception as e:
            logger.error(f"Database error during JP ticker sync: {e}")
            raise

    @track_performance("fetch_statements_jp")
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
                    logger.warning(f"No summary fallback available for {code}.")
                    return pd.DataFrame()
            else:
                logger.error(f"Critical error fetching statements for {code}: {e}")
                raise e
        return df

    @track_performance("fetch_and_ingest_statements_jp")
    def fetch_and_ingest_statements(self, code: str, session_id: str):
        """Fetch and ingest statements (Legacy synchronous method)."""
        df = self.fetch_statements(code)
        if df is None or df.empty:
            logger.info(f"No statements found for JP Ticker {code}.")
            return
        logger.info(f"Fetched {len(df)} financial records for JP Ticker {code}.")
        self.ingest_facts(code, df, session_id)

    @track_performance("ingest_facts_jp")
    def ingest_facts(self, code: str, df: pd.DataFrame, session_id: str):
        """Ingest J-Quants statement data into DuckDB using WIDE-FORMAT (Direct Column Mapping)."""
        try:
            if df is None or df.empty:
                return

            from src.core.contracts import JPFactContract

            # 2. Normalize Columns (V2 -> V1/Contract compatible)
            v2_mapping = {
                "DiscDate": "DisclosedDate",
                "DiscTime": "DisclosedTime",
                "Code": "LocalCode",
                "DiscNo": "DisclosureNumber",
                "DocType": "Type",
                "CurPerType": "FiscalPeriod",
                "Sales": "NetSales",
                "OP": "OperatingProfit",
                "OdP": "OrdinaryProfit",
                "NP": "Profit",
                "EPS": "EarningsPerShare",
                "TA": "TotalAssets",
                "Eq": "NetAssets",
                "EqAR": "EquityToAssetRatio",
                "BPS": "BookValuePerShare",
                "CFO": "CashFlowsFromOperatingActivities",
                "CFI": "CashFlowsFromInvestingActivities",
                "CFF": "CashFlowsFromFinancingActivities",
                "CashEq": "CashAndCashEquivalents",
            }
            # Only rename if columns exist (V2 detection)
            rename_map = {k: v for k, v in v2_mapping.items() if k in df.columns}
            if rename_map:
                df = df.rename(columns=rename_map)

            # Derive FiscalYear from CurFYEn if missing
            if "FiscalYear" not in df.columns and "CurFYEn" in df.columns:
                df["FiscalYear"] = (
                    df["CurFYEn"].astype(str).apply(lambda x: x.split("-")[0] if "-" in x else "")
                )

            # Ensure numeric fields are actually numeric (handle empty strings in V2)
            numeric_fields = [
                "NetSales",
                "OperatingProfit",
                "OrdinaryProfit",
                "Profit",
                "EarningsPerShare",
                "TotalAssets",
                "NetAssets",
                "Equity",
                "EquityToAssetRatio",
                "BookValuePerShare",
                "CashFlowsFromOperatingActivities",
                "CashFlowsFromInvestingActivities",
                "CashFlowsFromFinancingActivities",
                "CashAndCashEquivalents",
            ]
            for field in numeric_fields:
                if field in df.columns:
                    df[field] = pd.to_numeric(df[field], errors="coerce")

            # 1. Normalize Code (LocalCode or Code)
            code_col = "LocalCode"
            df["LocalCode"] = (
                df[code_col]
                .astype(str)
                .apply(
                    lambda c: c[:4]
                    if len(c) == self.JP_TICKER_LEN_WITH_ZERO and c.endswith("0")
                    else c
                )
            )

            # 2. Add Session ID and timestamps
            df["session_id"] = session_id

            # 3. Contract Validation & Cleaning
            # Filter for rows that meet the core contract
            valid_records = []
            for _, row in df.iterrows():
                try:
                    # We use model_validate and model_dump to ensure type safety and cleaning
                    # The contract defines the standard set of fields we want to persist.
                    contract = JPFactContract(**row.to_dict())
                    valid_records.append(contract.model_dump())
                except Exception as e:
                    logger.error(f"JP Fact validation failed for {code}: {e}")

            if not valid_records:
                logger.info(f"No valid JP fact records after validation for {code}.")
                return

            valid_df = pd.DataFrame(valid_records)

            # 4. Bulk Ingest to DuckDB (Wide Format)
            logger.info(f"Ingesting {len(valid_df)} wide-format records for JP Ticker {code}...")

            with db_manager.connect(self.db_path, read_only=settings.db_read_only) as conn:
                conn.execute(f"SET max_memory='{settings.DUCKDB_MEMORY_LIMIT}'")
                conn.execute(f"SET threads={settings.DUCKDB_THREADS}")
                conn.execute("PRAGMA disable_optimizer")

                # Dynamically build the INSERT list based on valid_df columns to match schema
                columns = [c for c in valid_df.columns if c != "ingested_at"]
                col_list = ", ".join(columns)
                val_list = ", ".join([f"source.{c}" for c in columns])

                conn.register("source_df", valid_df)
                query = f"""
                    INSERT OR IGNORE INTO company_facts ({col_list})
                    SELECT {val_list} FROM source_df AS source
                """  # noqa: S608
                conn.execute(query)
                logger.info(f"Successfully ingested JP facts for {code}.")
        except Exception as e:
            logger.error(f"Ingestion failed for JP Ticker {code}: {e}")
            raise



if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    engine = JPEngine()
    logger.info("JP Engine Initialized.")
