import logging
from pathlib import Path
import duckdb
import pandas as pd

logger = logging.getLogger(__name__)

class MacroEngine:
    """
    マクロ指標データの保存（Parquet）と抽出（DuckDB）を担当するエンジン。
    """
    def __init__(self, base_dir: str = "data/macro"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_safe_filename(self, symbol: str) -> str:
        # ファイル名に使えない文字を置換
        return symbol.replace(".", "_").replace("/", "_").replace("^", "_")

    def save_data(self, symbol: str, df: pd.DataFrame):
        if df.empty:
            return

        file_path = self.base_dir / f"{self._get_safe_filename(symbol)}.parquet"
        
        if file_path.exists():
            existing_df = pd.read_parquet(file_path)
            combined_df = pd.concat([existing_df, df], ignore_index=True)
            combined_df.to_parquet(file_path, index=False)
        else:
            df.to_parquet(file_path, index=False)
        
        logger.info(f"Saved {len(df)} rows for {symbol} to {file_path}")

    def get_latest_date(self, symbol: str) -> pd.Timestamp:
        file_path = self.base_dir / f"{self._get_safe_filename(symbol)}.parquet"
        if not file_path.exists():
            return pd.Timestamp("2000-01-01")
        try:
            with duckdb.connect(":memory:") as conn:
                res = conn.execute(f"SELECT MAX(Date) FROM read_parquet('{file_path}')").fetchone()
                return pd.Timestamp(res[0]) if res[0] else pd.Timestamp("2000-01-01")
        except Exception:
            return pd.Timestamp("2000-01-01")

    def get_values(self, symbol: str) -> list[dict]:
        file_path = self.base_dir / f"{self._get_safe_filename(symbol)}.parquet"
        if not file_path.exists():
            return []

        sql = f"""
        SELECT * EXCLUDE (row_num)
        FROM (
            SELECT *,
                   row_number() OVER (PARTITION BY Date ORDER BY LoadTimestamp DESC) as row_num
            FROM read_parquet('{file_path}')
        )
        WHERE row_num = 1
        ORDER BY Date ASC
        """
        try:
            with duckdb.connect(":memory:") as conn:
                df = conn.execute(sql).df()
                df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
                return df.to_dict(orient="records")
        except Exception as e:
            logger.error(f"Error querying data for {symbol}: {e}")
            return []
