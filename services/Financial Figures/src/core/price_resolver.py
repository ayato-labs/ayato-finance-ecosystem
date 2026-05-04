import logging

from src.core.db import db_manager

logger = logging.getLogger(__name__)


def get_safe_price_view_sql(parquet_path: str) -> str:
    """
    Returns a SQL snippet that creates a temporary view 'v_safe_prices'
    with normalized column names (ticker, date, close, open, high, low, volume).
    Uses DuckDB's case-insensitive COLUMNS regex matching.
    """
    # DuckDB's (?i) makes the regex case-insensitive
    return f"""
    CREATE OR REPLACE VIEW v_safe_prices AS
    SELECT
        COLUMNS('(?i)ticker') AS ticker,
        COLUMNS('(?i)date') AS date,
        COLUMNS('(?i)open') AS open,
        COLUMNS('(?i)high') AS high,
        COLUMNS('(?i)low') AS low,
        COLUMNS('(?i)close') AS close,
        COLUMNS('(?i)volume') AS volume
    FROM read_parquet('{parquet_path}', hive_partitioning=1)
    """  # nosec S608


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    price_path = (
        "C:/Users/saiha/My_Service/programing/finance/daily_stock_price/data/"
        "market_data/year=2026/month=04/*.parquet"
    )
    with db_manager.connect(":memory:") as conn:
        try:
            conn.execute(get_safe_price_view_sql(price_path))
            logger.info("Safe View Created. Testing column selection...")
            # Safe internal query for testing
            df = conn.execute("SELECT ticker, date, close FROM v_safe_prices LIMIT 1").df()
            logger.info(f"\n{df}")  # nosec S608
        except Exception as e:
            logger.error(f"Price resolver test failed: {e}")
