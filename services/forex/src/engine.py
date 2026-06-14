import threading
from pathlib import Path

import duckdb
import pandas as pd
from loguru import logger

_file_lock = threading.Lock()


class ForexEngine:
    """
    為替データの保存 (Parquet) と抽出 (DuckDB) を担当するエンジン。
    すべてのレートは '1 Unit = X USD' 形式で保存される。
    """

    def __init__(self, base_dir: str | None = None):
        if base_dir is None:
            # Resolve project root and set base directory
            project_root = Path(__file__).resolve().parents[3]
            self.base_dir = project_root / "data" / "forex"
        else:
            self.base_dir = Path(base_dir)
            
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_data(self, symbol: str, df: pd.DataFrame):
        if df.empty:
            return

        file_path = self.base_dir / f"{symbol}.parquet"

        with _file_lock:
            if file_path.exists():
                existing_df = pd.read_parquet(file_path)
                combined_df = pd.concat([existing_df, df], ignore_index=True)
                # 重複排除や統計破損防止のためインデックスをリセットして保存
                combined_df.reset_index(drop=True).to_parquet(file_path, index=False)
            else:
                df.reset_index(drop=True).to_parquet(file_path, index=False)

        logger.info(f"Saved {len(df)} rows for {symbol} to {file_path}")

    def get_latest_date(self, symbol: str) -> pd.Timestamp:
        file_path = self.base_dir / f"{symbol}.parquet"
        if not file_path.exists():
            return pd.Timestamp("2000-01-01")
        try:
            with duckdb.connect(":memory:") as conn:
                # 統計破損エラーを回避するための設定
                conn.execute("PRAGMA disable_optimizer")
                res = conn.execute(f"SELECT MAX(Date) FROM read_parquet('{file_path}')").fetchone()
                return pd.Timestamp(res[0]) if res[0] else pd.Timestamp("2000-01-01")
        except Exception:
            return pd.Timestamp("2000-01-01")

    def get_rates(self, symbol: str) -> list[dict]:
        """
        指定された通貨の対米ドルレート (USD基準) を取得する。
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
                conn.execute("PRAGMA disable_optimizer")
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
        最新の為替レート (1 Unit = X USD) を取得する。
        """
        if symbol == "USD":
            return 1.0

        file_path = self.base_dir / f"{symbol}.parquet"
        if not file_path.exists():
            return None

        try:
            with duckdb.connect(":memory:") as conn:
                conn.execute("PRAGMA disable_optimizer")
                query = f"SELECT Rate FROM read_parquet('{file_path}') ORDER BY Date DESC LIMIT 1"
                res = conn.execute(query).fetchone()
                val = res[0] if res else None
                return None if pd.isna(val) else val
        except Exception:
            return None
