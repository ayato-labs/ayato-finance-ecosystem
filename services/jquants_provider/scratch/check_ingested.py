import duckdb
from src.core.config import settings

def check_ingested():
    conn = duckdb.connect(str(settings.JP_PRICES_DB_PATH), read_only=True)
    df = conn.execute("""
        SELECT Date, Close, ingested_at 
        FROM daily_prices 
        WHERE Code = '7203' 
        ORDER BY Date DESC 
        LIMIT 5
    """).df()
    print(df.to_string())
    conn.close()

if __name__ == "__main__":
    check_ingested()
