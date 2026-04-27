from loguru import logger
from pathlib import Path
import duckdb
import pandas as pd
from datetime import datetime



class ForexEngine:
    """
    為替データの保存（Parquet）と抽出（DuckDB）を担当するエンジン。
    すべてのレートは '1 Unit = X USD' 形式で保存される。
    """
    def __init__(self, base_dir: str = "data/forex"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_data(self, symbol: str, df: pd.DataFrame):
        if df.empty:
            return

        file_path = self.base_dir / f"{symbol}.parquet"
        
        if file_path.exists():
            existing_df = pd.read_parquet(file_path)
            combined_df = pd.concat([existing_df, df], ignore_index=True)
            combined_df.to_parquet(file_path, index=False)
        else:
            df.to_parquet(file_path, index=False)
        
        logger.info(f"Saved {len(df)} rows for {symbol} to {file_path}")

    def get_latest_date(self, symbol: str) -> pd.Timestamp:
        file_path = self.base_dir / f"{symbol}.parquet"
        if not file_path.exists():
            return pd.Timestamp("2000-01-01")
        try:
            with duckdb.connect(":memory:") as conn:
                res = conn.execute(f"SELECT MAX(Date) FROM read_parquet('{file_path}')").fetchone()
                return pd.Timestamp(res[0]) if res[0] else pd.Timestamp("2000-01-01")
        except Exception:
            return pd.Timestamp("2000-01-01")

    def get_rates(self, symbol: str) -> list[dict]:
        """
        指定された通貨の対米ドルレート（USD基準）を取得する。
        """
        file_path = self.base_dir / f"{symbol}.parquet"
        if not file_path.exists():
            return []

        # 重複排除ロジック: 同じ日付のデータがある場合、LoadTimestampが新しい方を優先
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
                records = df.to_dict(orient="records")
                # Replace NaN with None for JSON compliance
                return [{k: (None if pd.isna(v) else v) for k, v in r.items()} for r in records]
        except Exception as e:
            logger.error(f"Error querying forex data for {symbol}: {e}")
            return []

    def get_latest_rate(self, symbol: str) -> float:
        """
        最新の為替レート（1 Unit = X USD）を取得する。
        """
        if symbol == "USD":
            return 1.0
            
        file_path = self.base_dir / f"{symbol}.parquet"
        if not file_path.exists():
            return None
            
        try:
            with duckdb.connect(":memory:") as conn:
                res = conn.execute(f"SELECT Rate FROM read_parquet('{file_path}') ORDER BY Date DESC LIMIT 1").fetchone()
                val = res[0] if res else None
                return None if pd.isna(val) else val
        except Exception:
            return None
