import duckdb
from pathlib import Path

data_dir = Path("data")
for db_file in data_dir.glob("*.duckdb"):
    print(f"--- Checking {db_file.name} ---")
    try:
        with duckdb.connect(str(db_file), read_only=True) as conn:
            # Check if table exists
            tables = conn.execute("SHOW TABLES").fetchall()
            table_names = [t[0] for t in tables]
            if "daily_prices" in table_names:
                schema = conn.execute("DESCRIBE daily_prices").fetchall()
                for col in schema:
                    if col[0] in ('TurnoverValue', 'Open', 'High', 'Low', 'Close'):
                        print(f"  {col[0]}: {col[1]}")
            else:
                print("  Table 'daily_prices' not found.")
    except Exception as e:
        print(f"  Error: {e}")
