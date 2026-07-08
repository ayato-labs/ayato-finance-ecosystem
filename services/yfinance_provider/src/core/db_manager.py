from pathlib import Path

import duckdb

from .db_schema import generate_schema_files
from .logging import setup_logger

logger = setup_logger(app_name="db_manager")


class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Schema-as-Code: スキーマ定義とマイグレーションの初期化"""
        logger.info(f"Initializing/Migrating Database at {self.db_path}")
        try:
            # Auto-generate schema.sql and database_design.md
            db_dir = Path(self.db_path).parent
            generate_schema_files(db_dir)

            conn = duckdb.connect(self.db_path)

            # マスター管理テーブル (SSoT)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_status (
                    ticker VARCHAR PRIMARY KEY,
                    last_sync_at TIMESTAMP,
                    last_status VARCHAR,
                    error_message TEXT,
                    quality_score DOUBLE,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 財務データテーブル
            conn.execute("""
                CREATE TABLE IF NOT EXISTS info (
                    ticker VARCHAR PRIMARY KEY,
                    data JSON,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS financials (
                    ticker VARCHAR,
                    date DATE,
                    item VARCHAR,
                    value DOUBLE,
                    period_type VARCHAR,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (ticker, date, item, period_type)
                );
                CREATE TABLE IF NOT EXISTS balance_sheet (
                    ticker VARCHAR,
                    date DATE,
                    item VARCHAR,
                    value DOUBLE,
                    period_type VARCHAR,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (ticker, date, item, period_type)
                );
                CREATE TABLE IF NOT EXISTS cashflow (
                    ticker VARCHAR,
                    date DATE,
                    item VARCHAR,
                    value DOUBLE,
                    period_type VARCHAR,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (ticker, date, item, period_type)
                );
                CREATE TABLE IF NOT EXISTS prices (
                    ticker VARCHAR,
                    date TIMESTAMP,
                    open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE,
                    volume BIGINT, dividends DOUBLE, stock_splits DOUBLE,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (ticker, date)
                );
                CREATE TABLE IF NOT EXISTS forex_rates (
                    symbol VARCHAR,
                    date DATE,
                    rate DOUBLE,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (symbol, date)
                );
                CREATE TABLE IF NOT EXISTS crypto_metadata (
                    ticker VARCHAR PRIMARY KEY,
                    circulating_supply DOUBLE,
                    total_supply DOUBLE,
                    max_supply DOUBLE,
                    market_cap DOUBLE,
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.close()
            logger.success("Database migration completed successfully.")
        except Exception:
            logger.exception("Failed to initialize database")
            raise

    def get_connection(self):
        return duckdb.connect(self.db_path)

    def update_sync_status(
        self,
        ticker: str,
        status: str,
        error: str | None = None,
        score: float = 1.0,
        conn=None,
    ):
        """同期ステータスの更新。connが渡された場合はそれを使用し、閉じない。"""
        try:
            should_close = False
            if conn is None:
                conn = self.get_connection()
                should_close = True

            query = """
                INSERT OR REPLACE INTO sync_status
                (ticker, last_sync_at, last_status, error_message, quality_score)
                VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?)
            """
            conn.execute(query, [ticker, status, error, score])

            if should_close:
                conn.close()
        except Exception:
            logger.exception(f"Failed to update sync status for {ticker}")
