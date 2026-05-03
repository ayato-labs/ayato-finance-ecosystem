from pathlib import Path

import duckdb
import pandas as pd
from loguru import logger

class CryptoDBEngine:
    def __init__(self, db_path: str = "data/crypto_prices.duckdb"):
        self.db_path = db_path
        # Ensure the directory exists
        path = Path(db_path)
        if path.parent:
            path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with duckdb.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS prices (
                    ticker VARCHAR,
                    date DATE,
                    open DOUBLE,
                    high DOUBLE,
                    low DOUBLE,
                    close DOUBLE,
                    volume DOUBLE,
                    PRIMARY KEY (ticker, date)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    ticker VARCHAR PRIMARY KEY,
                    circulating_supply DOUBLE,
                    total_supply DOUBLE,
                    max_supply DOUBLE,
                    market_cap DOUBLE,
                    description TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info(f"Database initialized at {self.db_path}")

    def save_prices(self, ticker: str, df: pd.DataFrame):
        if df.empty:
            return

        df["ticker"] = ticker

        with duckdb.connect(self.db_path) as conn:
            # Use UPSERT logic (Delete then Insert)
            conn.execute("CREATE TEMPORARY TABLE temp_prices AS SELECT * FROM df")
            conn.execute("""
                DELETE FROM prices
                WHERE (ticker, date) IN (SELECT ticker, CAST(date AS DATE) FROM temp_prices)
            """)
            conn.execute("""
                INSERT INTO prices
                SELECT ticker, CAST(date AS DATE), open, high, low, close, volume FROM temp_prices
            """)
            logger.info(f"Saved {len(df)} records for {ticker}")

    def get_prices(self, ticker: str):
        with duckdb.connect(self.db_path) as conn:
            query = """
                SELECT ticker, CAST(date AS VARCHAR) as Date,
                       open as Open, high as High, low as Low, close as Close, volume as Volume
                FROM prices WHERE ticker = ? ORDER BY date ASC
            """
            df = conn.execute(query, [ticker]).df()
            return df.to_dict(orient="records")

    def save_metadata(self, ticker: str, meta: dict):
        with duckdb.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO metadata
                (ticker, circulating_supply, total_supply, max_supply, market_cap,
                 description, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, [
                ticker,
                meta.get("circulating_supply"),
                meta.get("total_supply"),
                meta.get("max_supply"),
                meta.get("market_cap"),
                meta.get("description")
            ])
            logger.info(f"Saved metadata for {ticker}")

    def get_metadata(self, ticker: str):
        with duckdb.connect(self.db_path) as conn:
            # DuckDB returns tuples
            res = conn.execute("SELECT * FROM metadata WHERE ticker = ?", [ticker]).fetchone()
            if not res:
                return None
            return {
                "ticker": res[0],
                "circulating_supply": res[1],
                "total_supply": res[2],
                "max_supply": res[3],
                "market_cap": res[4],
                "description": res[5],
                "last_updated": str(res[6])
            }
