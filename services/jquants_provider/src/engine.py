import pandas as pd
import datetime
from pathlib import Path
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.core.config import settings
from src.core.db import db_manager
from src.core.logging import track_performance
from src.core.rate_limit import rate_limit
from src.core.catalog import catalog_manager

try:
    import jquantsapi
except ImportError:
    jquantsapi = None


class JPEngine:
    JP_TICKER_LEN_WITH_ZERO = 5

    def __init__(self, api_key: str | None = None, refresh_token: str | None = None):
        self.api_key = api_key if api_key is not None else settings.JQUANTS_API_KEY
        self.refresh_token = (
            refresh_token if refresh_token is not None else settings.JQUANTS_REFRESH_TOKEN
        )
        self._lookup_cache = {}  # Cache for market/sector IDs

        if not jquantsapi:
            raise ImportError("jquants-api-client is not installed.")

        if self.refresh_token and len(str(self.refresh_token).strip()) > 0:
            logger.info("Using J-Quants V1 Client")
            self.cli = jquantsapi.Client(refresh_token=self.refresh_token)
        elif self.api_key and len(str(self.api_key).strip()) > 0:
            logger.info("Using J-Quants V2 Client")
            self.cli = jquantsapi.ClientV2(api_key=self.api_key)
        else:
            raise ValueError("No J-Quants credentials found.")

        self._init_db()

    def _get_shard_path(self, table_name: str) -> Path:
        """Get the physical database path for a given table name."""
        from src.core.schema import TABLE_SCHEMAS
        shard_name = TABLE_SCHEMAS.get(table_name, {}).get("shard", "master")
        
        if shard_name == "prices":
            return settings.JP_PRICES_DB_PATH
        if shard_name == "financials":
            return settings.JP_FACTS_DB_PATH
        return settings.JP_MASTER_DB_PATH

    def _init_db(self):
        from src.core.migrations import MigrationManager
        MigrationManager.apply_migrations()

    def get_latest_price_date(self) -> str | None:
        """Get the latest price date in YYYYMMDD format."""
        db_path = self._get_shard_path("daily_prices")
        with db_manager.connect(db_path) as conn:
            res = conn.execute("SELECT MAX(Date) FROM daily_prices").fetchone()
            if res and res[0]:
                return res[0].strftime("%Y%m%d")
        return None

    def get_earliest_price_date(self) -> str | None:
        """Get the earliest price date in YYYYMMDD format."""
        db_path = self._get_shard_path("daily_prices")
        with db_manager.connect(db_path) as conn:
            try:
                res = conn.execute("SELECT MIN(Date) FROM daily_prices").fetchone()
                if res and res[0]:
                    return res[0].strftime("%Y%m%d")
            except Exception:
                pass
        return None

    def get_latest_fact_date(self) -> str | None:
        """Get the latest fact date in YYYYMMDD format."""
        db_path = self._get_shard_path("company_facts")
        with db_manager.connect(db_path) as conn:
            res = conn.execute("SELECT MAX(DisclosedDate) FROM company_facts").fetchone()
            if res and res[0]:
                return res[0].strftime("%Y%m%d")
        return None

    def get_earliest_fact_date(self) -> str | None:
        """Get the earliest fact date in YYYYMMDD format."""
        db_path = self._get_shard_path("company_facts")
        with db_manager.connect(db_path) as conn:
            try:
                res = conn.execute("SELECT MIN(DisclosedDate) FROM company_facts").fetchone()
                if res and res[0]:
                    return res[0].strftime("%Y%m%d")
            except Exception:
                pass
        return None

    @track_performance("sync_tickers_jp")
    @rate_limit
    @retry(
        wait=wait_exponential(multiplier=5, min=30, max=600),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(Exception),
        before_sleep=lambda retry_state: logger.warning(
            f"Retrying Ticker sync ({retry_state.attempt_number}/5) after {retry_state.outcome.exception()}"
        ),
        reraise=True,
    )
    def sync_tickers(self, session_id: str | None = None) -> int:
        return self._sync_tickers_logic(session_id)

    def _get_lookup_id(self, table_name: str, name: str) -> int:
        """Get or create a lookup ID for a normalized name with caching."""
        if not name:
            return 0
        
        cache_key = (table_name, name)
        if cache_key in self._lookup_cache:
            return self._lookup_cache[cache_key]

        db_path = self._get_shard_path(table_name)
        with db_manager.connect(db_path) as conn:
            res = conn.execute(f"SELECT id FROM {table_name} WHERE name = ?", (name,)).fetchone()
            if res:
                self._lookup_cache[cache_key] = res[0]
                return res[0]
            
            # Create new ID
            max_id = conn.execute(f"SELECT MAX(id) FROM {table_name}").fetchone()[0] or 0
            new_id = max_id + 1
            conn.execute(f"INSERT INTO {table_name} (id, name) VALUES (?, ?)", (new_id, name))
            self._lookup_cache[cache_key] = new_id
            return new_id

    def _sync_tickers_logic(self, session_id: str | None = None) -> int:
        if hasattr(self.cli, "get_list"):
            df = self.cli.get_list()
        else:
            df = self.cli.get_stock_list()

        if df is None or df.empty:
            return 0

        # Mapping to match API fields
        mapping = {"Code": "code", "CoName": "name", "MktNm": "market_section", "S17Nm": "sector"}
        df = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})

        from src.core.contracts import JPTickerContract

        valid_records = []
        for _, row in df.iterrows():
            try:
                # Normalize metadata
                m_id = self._get_lookup_id("market_sections", row.get("market_section"))
                s_id = self._get_lookup_id("sectors", row.get("sector"))
                
                contract = JPTickerContract(
                    code=row["code"],
                    name=row["name"],
                    market_section_id=m_id,
                    sector_id=s_id,
                    last_session_id=session_id
                )
                valid_records.append(contract.model_dump())
            except Exception as e:
                logger.error(f"Ticker validation failed: {e}")

        if not valid_records:
            return 0

        valid_df = pd.DataFrame(valid_records)
        db_path = self._get_shard_path("tickers")
        with db_manager.connect(db_path) as conn:
            conn.execute(f"SET max_memory='{settings.DUCKDB_MEMORY_LIMIT}'")
            conn.execute(f"SET threads={settings.DUCKDB_THREADS}")
            conn.register("source_df", valid_df)
            conn.execute(
                "INSERT OR REPLACE INTO tickers (code, name, market_section_id, sector_id, last_session_id) SELECT * FROM source_df"
            )

        catalog_manager.update_shard_status(
            self.shard_name, self.db_path, 2, records_count=len(valid_df)
        )
        return len(valid_df)

    @rate_limit
    @retry(
        wait=wait_exponential(multiplier=2, min=5, max=60),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def fetch_statements(self, code: str) -> pd.DataFrame:
        df = pd.DataFrame()
        try:
            if hasattr(self.cli, "get_fin_details"):
                df = self.cli.get_fin_details(code=code)
            else:
                df = self.cli.get_statements(code=code)
        except Exception as e:
            if any(err in str(e) for err in ["403", "400"]):
                logger.debug(f"Plan restriction or missing data for {code}: {e}")
                if hasattr(self.cli, "get_fin_summary"):
                    df = self.cli.get_fin_summary(code=code)
                return df  # Return empty or summary instead of retrying 403
            if "429" in str(e):
                raise e  # Trigger retry for 429
            raise e
        return df

    @track_performance("fetch_daily_bars_api")
    @rate_limit
    @retry(
        wait=wait_exponential(multiplier=5, min=65, max=300),  # Wait at least 65s for 429 to clear
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def fetch_daily_bars(self, date_str: str) -> pd.DataFrame:
        """Fetch daily bars for a specific date."""
        try:
            if hasattr(self.cli, "get_eq_bars_daily"):
                return self.cli.get_eq_bars_daily(date=date_str)
            return self.cli.get_prices_daily(date=date_str)
        except Exception as e:
            # Try to extract detailed message from J-Quants response if available
            error_msg = str(e)
            if hasattr(e, "response") and e.response is not None:
                try:
                    detail = e.response.json()
                    error_msg = f"{e} - API Detail: {detail}"
                except:
                    error_msg = f"{e} - Body: {e.response.text}"
            logger.error(f"J-Quants API Error (Bars): {error_msg}")
            raise e

    @rate_limit
    @retry(
        wait=wait_exponential(multiplier=5, min=65, max=300),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def fetch_fin_summary(self, date_str: str) -> pd.DataFrame:
        """Fetch financial summaries for a specific date."""
        try:
            if hasattr(self.cli, "get_fin_summary"):
                return self.cli.get_fin_summary(date=date_str)
            return pd.DataFrame()
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "response") and e.response is not None:
                try:
                    detail = e.response.json()
                    error_msg = f"{e} - API Detail: {detail}"
                except:
                    error_msg = f"{e} - Body: {e.response.text}"
            logger.error(f"J-Quants API Error (Financials): {error_msg}")
            raise e

    def fetch_prices_range(self, start_date: str, end_date: str, session_id: str | None = None) -> pd.DataFrame:
        """Fetch historical daily bars for a date range sequentially to respect rate limits."""
        all_dfs = []
        current = datetime.datetime.strptime(start_date, "%Y%m%d").date()
        end = datetime.datetime.strptime(end_date, "%Y%m%d").date()
        
        total_days = (end - current).days + 1
        logger.info(f"Sequential range fetch: {start_date} to {end_date} ({total_days} days)")
        
        while current <= end:
            date_str = current.strftime("%Y%m%d")
            # fetch_daily_bars is already decorated with @rate_limit and @retry
            df = self.fetch_daily_bars(date_str)
            if df is not None and not df.empty:
                logger.info(f"Ingesting {len(df)} price records for {date_str}")
                self.ingest_prices(df, session_id)
                all_dfs.append(df)
            current += datetime.timedelta(days=1)
            
        return pd.concat(all_dfs) if all_dfs else pd.DataFrame()

    def fetch_fin_range(self, start_date: str, end_date: str, session_id: str | None = None) -> pd.DataFrame:
        """Fetch financial summaries for a date range sequentially to respect rate limits."""
        all_dfs = []
        current = datetime.datetime.strptime(start_date, "%Y%m%d").date()
        end = datetime.datetime.strptime(end_date, "%Y%m%d").date()
        
        total_days = (end - current).days + 1
        logger.info(f"Sequential financial fetch: {start_date} to {end_date} ({total_days} days)")
        
        while current <= end:
            date_str = current.strftime("%Y%m%d")
            # fetch_fin_summary is already decorated with @rate_limit and @retry
            df = self.fetch_fin_summary(date_str)
            if df is not None and not df.empty:
                logger.info(f"Ingesting {len(df)} financial records for {date_str}")
                self.ingest_facts(df, session_id)
                all_dfs.append(df)
            current += datetime.timedelta(days=1)
            
        return pd.concat(all_dfs) if all_dfs else pd.DataFrame()

    @track_performance("ingest_facts_jp")
    def ingest_facts(self, df: pd.DataFrame, session_id: str):
        if df is None or df.empty:
            logger.info("No financial fact data to ingest.")
            return

        logger.info(f"Preparing to ingest {len(df)} financial fact records...")
        from src.core.contracts import JPFactContract

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
        
        try:
            df = df.rename(columns={k: v for k, v in v2_mapping.items() if k in df.columns})

            if "FiscalYear" not in df.columns and "CurFYEn" in df.columns:
                df["FiscalYear"] = (
                    df["CurFYEn"].astype(str).apply(lambda x: x.split("-")[0] if "-" in x else "")
                )

            numeric_fields = settings.JQUANTS_V2_LABELS
            for field in numeric_fields:
                if field in df.columns:
                    df[field] = pd.to_numeric(df[field], errors="coerce")

            df["LocalCode"] = (
                df["LocalCode"]
                .astype(str)
                .apply(lambda c: c[:4] if len(c) == 5 and c.endswith("0") else c)
            )
            df["session_id"] = session_id
        except Exception as e:
            logger.error(f"Data preprocessing failed for financials: {e}")
            raise

        valid_records = []
        error_count = 0
        for _, row in df.iterrows():
            try:
                contract = JPFactContract(**row.to_dict())
                valid_records.append(contract.model_dump())
            except Exception as e:
                error_count += 1
                if error_count < 10:  # Avoid log flooding
                    logger.debug(f"Fact validation skipped for {row.get('LocalCode', 'unknown')}: {e}")

        if error_count > 0:
            logger.warning(f"Skipped {error_count} invalid financial records during validation.")

        if not valid_records:
            logger.warning("No valid financial records remained after validation.")
            return

        valid_df = pd.DataFrame(valid_records)

        db_path = self._get_shard_path("company_facts")
        try:
            with db_manager.connect(db_path) as conn:
                conn.execute(f"SET max_memory='{settings.DUCKDB_MEMORY_LIMIT}'")
                conn.execute(f"SET threads={settings.DUCKDB_THREADS}")
                columns = [c for c in valid_df.columns if c != "ingested_at"]
                col_list = ", ".join(columns)
                val_list = ", ".join([f"source.{c}" for c in columns])
                conn.register("source_df", valid_df)
                conn.execute(
                    f"INSERT OR IGNORE INTO company_facts ({col_list}) SELECT {val_list} FROM source_df AS source"
                )
                logger.info(f"Successfully ingested {len(valid_df)} financial records into company_facts.")
                
                catalog_manager.update_shard_status(
                    self.shard_name, self.db_path, 2, records_count=len(valid_df)
                )
        except Exception as e:
            logger.error(f"Database ingestion failed for financials: {e}")
            raise

    @track_performance("ingest_prices_jp")
    def ingest_prices(self, df: pd.DataFrame, session_id: str):
        """Ingest daily stock prices into DuckDB."""
        if df is None or df.empty:
            logger.info("No price data to ingest.")
            return

        logger.info(f"Preparing to ingest {len(df)} price records...")
        from src.core.contracts import JPPriceContract

        try:
            v2_price_mapping = {
                "O": "Open", "H": "High", "L": "Low", "C": "Close", "Vo": "Volume",
                "AdjO": "AdjustmentOpen", "AdjH": "AdjustmentHigh", "AdjL": "AdjustmentLow",
                "AdjC": "AdjustmentClose", "AdjVo": "AdjustmentVolume", "Va": "TurnoverValue",
            }
            logger.debug(f"Raw API columns: {df.columns.tolist()}")
            if not df.empty:
                logger.debug(f"Sample row: {df.iloc[0].to_dict()}")
            df = df.rename(columns={k: v for k, v in v2_price_mapping.items() if k in df.columns})
            df["session_id"] = session_id
            if "Code" in df.columns:
                df["Code"] = (
                    df["Code"]
                    .astype(str)
                    .apply(lambda c: c[:4] if len(c) == 5 and c.endswith("0") else c)
                )
        except Exception as e:
            logger.error(f"Data preprocessing failed for prices: {e}")
            raise

        valid_records = []
        error_count = 0
        for _, row in df.iterrows():
            try:
                contract = JPPriceContract(**row.to_dict())
                valid_records.append(contract.model_dump())
            except Exception as e:
                error_count += 1
                if error_count < 5:
                    logger.debug(f"Price validation failed for {row.get('Code', 'unknown')} on {row.get('Date')}: {e}")

        if error_count > 0:
            logger.warning(f"Skipped {error_count} invalid price records.")

        if not valid_records:
            return

        valid_df = pd.DataFrame(valid_records)

        db_path = self._get_shard_path("daily_prices")
        try:
            with db_manager.connect(db_path) as conn:
                conn.execute(f"SET max_memory='{settings.DUCKDB_MEMORY_LIMIT}'")
                conn.execute(f"SET threads={settings.DUCKDB_THREADS}")
                columns = [c for c in valid_df.columns if c != "ingested_at"]
                col_list = ", ".join(columns)
                val_list = ", ".join([f"source.{c}" for c in columns])
                conn.register("source_df", valid_df)
                conn.execute(
                    f"INSERT OR IGNORE INTO daily_prices ({col_list}) SELECT {val_list} FROM source_df AS source"
                )
                logger.info(f"Successfully ingested {len(valid_df)} price records into daily_prices.")
                catalog_manager.update_shard_status(
                    "prices", db_path, 3, records_count=len(valid_df)
                )
        except Exception as e:
            logger.error(f"Database ingestion failed for prices: {e}")
            raise

    @track_performance("ingest_indices_jp")
    def ingest_indices(self, df: pd.DataFrame, session_id: str):
        """Ingest daily index quotes into DuckDB."""
        if df is None or df.empty:
            return

        from src.core.contracts import JPIndexContract

        df["session_id"] = session_id
        valid_records = []
        for _, row in df.iterrows():
            try:
                contract = JPIndexContract(**row.to_dict())
                valid_records.append(contract.model_dump())
            except Exception as e:
                logger.error(f"Index validation failed: {e}")

        if not valid_records:
            return

        valid_df = pd.DataFrame(valid_records)
        db_path = self._get_shard_path("indices")
        with db_manager.connect(db_path) as conn:
            columns = [c for c in valid_df.columns if c != "ingested_at"]
            col_list = ", ".join(columns)
            val_list = ", ".join([f"source.{c}" for c in columns])
            conn.register("source_df", valid_df)
            conn.execute(
                f"INSERT OR IGNORE INTO daily_indices ({col_list}) SELECT {val_list} FROM source_df AS source"
            )
            logger.info(f"Successfully ingested {len(valid_df)} index records.")
            catalog_manager.update_shard_status(
                "master", db_path, 1, records_count=len(valid_df)
            )

    @track_performance("ingest_dividends_jp")
    def ingest_dividends(self, df: pd.DataFrame, session_id: str):
        """Ingest dividend information into DuckDB."""
        if df is None or df.empty:
            return

        from src.core.contracts import JPDividendContract

        df["session_id"] = session_id
        if "Code" in df.columns:
            df["Code"] = (
                df["Code"]
                .astype(str)
                .apply(lambda c: c[:4] if len(c) == 5 and c.endswith("0") else c)
            )

        valid_records = []
        for _, row in df.iterrows():
            try:
                contract = JPDividendContract(**row.to_dict())
                valid_records.append(contract.model_dump())
            except Exception as e:
                logger.error(f"Dividend validation failed: {e}")

        if not valid_records:
            return

        valid_df = pd.DataFrame(valid_records)
        db_path = self._get_shard_path("dividends")
        with db_manager.connect(db_path) as conn:
            columns = [c for c in valid_df.columns if c != "ingested_at"]
            col_list = ", ".join(columns)
            val_list = ", ".join([f"source.{c}" for c in columns])
            conn.register("source_df", valid_df)
            conn.execute(
                f"INSERT OR IGNORE INTO dividends ({col_list}) SELECT {val_list} FROM source_df AS source"
            )
            logger.info(f"Successfully ingested {len(valid_df)} dividend records.")
            catalog_manager.update_shard_status(
                "financials", db_path, 1, records_count=len(valid_df)
            )
