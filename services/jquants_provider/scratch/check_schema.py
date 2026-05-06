import duckdb
from src.core.config import settings

def check_schema():
    print(f"Checking prices shard: {settings.JP_PRICES_DB_PATH}")
    conn = duckdb.connect(str(settings.JP_PRICES_DB_PATH))
    res = conn.execute("DESCRIBE daily_prices").fetchall()
    for row in res:
        print(f"Column: {row[0]}, Type: {row[1]}")
    conn.close()

if __name__ == "__main__":
    check_schema()
