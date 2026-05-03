from pathlib import Path

import duckdb
import pandas as pd
from loguru import logger



class IndexEngine:
    """
    指数データの保存 (Parquet) と抽出 (DuckDB) を担当するエンジン。
    """
    def __init__(self, base_dir: str = "data/market_index"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_data(self, ticker: str, df: pd.DataFrame):
        """
        データをティッカーごとのParquetファイルとして保存する。
        """
        if df.empty:
            return

        # ティッカー名を安全なファイル名に変換 (^GSPC -> _GSPC)
        safe_ticker = ticker.replace("^", "_")
        file_path = self.base_dir / f"{safe_ticker}.parquet"

        # 既存データがある場合は追記 (実際は重複を含めて保存し、読込時に排除する)
        if file_path.exists():
            existing_df = pd.read_parquet(file_path)
            combined_df = pd.concat([existing_df, df], ignore_index=True)
            combined_df.to_parquet(file_path, index=False)
        else:
            df.to_parquet(file_path, index=False)

        logger.info(f"Saved {len(df)} rows for {ticker} to {file_path}")

    def get_latest_date(self, ticker: str) -> pd.Timestamp:
        """
        保存されているデータの最新日付を取得する。
        """
        safe_ticker = ticker.replace("^", "_")
        file_path = self.base_dir / f"{safe_ticker}.parquet"
        
        if not file_path.exists():
            return pd.Timestamp("2000-01-01")

        try:
            with duckdb.connect(":memory:") as conn:
                res = conn.execute(f"SELECT MAX(Date) FROM read_parquet('{file_path}')").fetchone()
                return pd.Timestamp(res[0]) if res[0] else pd.Timestamp("2000-01-01")
        except Exception:
            return pd.Timestamp("2000-01-01")

    def get_prices(self, ticker: str) -> list[dict]:
        """
        DuckDBを使用して、重複を排除した最新の価格データを取得する。
        """
        safe_ticker = ticker.replace("^", "_")
        file_path = self.base_dir / f"{safe_ticker}.parquet"
        
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
                # 日付を文字列に変換
                df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
                records = df.to_dict(orient="records")
                # Replace NaN with None for JSON compliance
                return [{k: (None if pd.isna(v) else v) for k, v in r.items()} for r in records]
        except Exception as e:
            logger.error(f"Error querying data for {ticker}: {e}")
            return []
