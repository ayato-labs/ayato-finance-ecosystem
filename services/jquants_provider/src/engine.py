import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import duckdb
import pandas as pd
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

try:
    import jquantsapi
except ImportError:
    jquantsapi = None


class DuckDBManager:
    """DuckDB 接続を管理し、ファイルロックをハンドリングするクラス"""

    _local_lock = threading.Lock()

    @staticmethod
    @contextmanager
    def connect(db_path: str | Path, read_only: bool = False, timeout_seconds: int = 30):
        db_path_str = str(db_path)
        start_time = time.time()
        conn = None

        while time.time() - start_time < timeout_seconds:
            try:
                with DuckDBManager._local_lock:
                    conn = duckdb.connect(db_path_str, read_only=read_only)
                break
            except (duckdb.IOException, OSError) as e:
                err_msg = str(e).lower()
                if any(kw in err_msg for kw in ["io error", "locked", "used by", "permission"]):
                    time.sleep(1.0)
                else:
                    raise e

        if conn is None:
            raise duckdb.IOException(f"Failed to acquire database lock for {db_path}")

        try:
            yield conn
        finally:
            if conn:
                conn.close()


class JPEngine:
    JP_TICKER_LEN_WITH_ZERO = 5

    def __init__(self, api_key: str | None = None, refresh_token: str | None = None):
        """
        J-Quants API エンジンの初期化
        """
        self.db_path = Path("data/jquants.duckdb")
        self.api_key = api_key or os.environ.get("JQUANTS_API_KEY")
        self.refresh_token = refresh_token or os.environ.get("JQUANTS_REFRESH_TOKEN")

        if not jquantsapi:
            raise ImportError("jquants-api-client is not installed.")

        # V1 (Refresh Token) > V2 (API Key) の優先順位でクライアントを初期化
        if self.refresh_token:
            logger.info("Using J-Quants V1 Client")
            self.cli = jquantsapi.Client(refresh_token=self.refresh_token)
        elif self.api_key:
            logger.info("Using J-Quants V2 Client")
            self.cli = jquantsapi.ClientV2(api_key=self.api_key)
        else:
            raise ValueError("No J-Quants credentials found (JQUANTS_API_KEY or REFRESH_TOKEN)")

        self._init_db()

    def _init_db(self):
        """データベースの初期化"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with DuckDBManager.connect(self.db_path) as conn:
            conn.execute("SET max_memory='2GB'")
            conn.execute("SET threads=4")
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
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jp_facts_lookup "
                "ON company_facts (code, tag, disclosed_date)"
            )

    @retry(
        wait=wait_exponential(multiplier=2, min=4, max=60),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def sync_tickers(self, session_id: str = "manual-sync") -> int:
        """上場銘録を取得・同期"""
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

        df_mapped = pd.DataFrame(
            {
                "code": normalized_codes,
                "name": df[name_col],
                "market_section": df.get("MarketCodeName", df.get("Section", "")),
                "sector": df.get("Sector17CodeName", ""),
                "last_session_id": session_id,
            }
        )

        with DuckDBManager.connect(self.db_path) as conn:
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
        """財務諸表データの取得"""
        df = pd.DataFrame()
        try:
            if hasattr(self.cli, "get_fin_details"):
                df = self.cli.get_fin_details(code=code)
            else:
                df = self.cli.get_statements(code=code)
        except Exception as e:
            if any(err in str(e) for err in ["403", "400", "429"]):
                logger.info(f"Fallback to summary for {code}. (Error: {e})")
                if hasattr(self.cli, "get_fin_summary"):
                    df = self.cli.get_fin_summary(code=code)
            else:
                raise e
        return df

    def ingest_facts(self, code: str, df: pd.DataFrame, session_id: str):
        """財務データの DuckDB へのインジェスト（ベクトル化処理）"""
        if df is None or df.empty:
            return

        date_options = ["DisclosedDate", "Date", "DiscDate"]
        date_col = next((c for c in date_options if c in df.columns), None)
        if not date_col:
            return

        ignore_cols = [
            "LocalCode", "DisclosedDate", "FiscalYear", "FiscalPeriod", "DocType",
            "CurPerType", "CurPerSt", "CurPerEn", "CurFYSt", "CurFYEn", "NxtFYSt", "NxtFYEn",
            "DEPS", "REPS", "Type", "Code",
        ]

        id_vars = [
            c for c in [date_col, "LocalCode", "Code", "FiscalYear", "FiscalPeriod"]
            if c in df.columns
        ]

        melted = df.melt(id_vars=id_vars, var_name="tag", value_name="value")
        melted = melted[~melted["tag"].isin(ignore_cols)]
        melted = melted.dropna(subset=["value"])
        melted["value"] = pd.to_numeric(melted["value"], errors="coerce")
        melted = melted.dropna(subset=["value"])

        if melted.empty:
            return

        melted["code"] = melted.get("LocalCode", melted.get("Code", code)).astype(str)
        melted["code"] = melted["code"].apply(
            lambda c: c[:4] if len(c) == self.JP_TICKER_LEN_WITH_ZERO and c.endswith("0") else c
        )

        melted["disclosed_date"] = pd.to_datetime(melted[date_col]).dt.strftime("%Y-%m-%d")
        melted["fiscal_year"] = melted.get("FiscalYear")
        melted["fiscal_period"] = melted.get("FiscalPeriod")
        melted["taxonomy"] = "JP-GAAP"
        melted["label"] = melted["tag"]
        melted["unit"] = "JPY"
        melted["session_id"] = session_id
        melted["accession_number"] = melted["code"] + "-" + melted["disclosed_date"]

        logger.info(f"Ingesting {len(melted)} fact records for {code}...")

        with DuckDBManager.connect(self.db_path) as conn:
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
                FROM melted
                """
            )
