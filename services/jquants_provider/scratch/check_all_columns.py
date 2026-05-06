import duckdb
from pathlib import Path

data_dir = Path("data")
db_file = data_dir / "jquants_prices.duckdb"
print(f"--- Checking {db_file.name} ---")
try:
    with duckdb.connect(str(db_file), read_only=True) as conn:
        schema = conn.execute("DESCRIBE daily_prices").fetchall()
        for col in schema:
            print(f"  {col[0]}: {col[1]}")
except Exception as e:
    print(f"  Error: {e}")
