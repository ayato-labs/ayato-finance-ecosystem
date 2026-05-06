import duckdb
from pathlib import Path

db_path = Path("data/jquants.duckdb")

def inspect_schema():
    if not db_path.exists():
        print("Database not found.")
        return
    conn = duckdb.connect(str(db_path))
    print("=== Schema for daily_prices ===")
    print(conn.execute("PRAGMA table_info('daily_prices')").df())
    conn.close()

if __name__ == "__main__":
    inspect_schema()
