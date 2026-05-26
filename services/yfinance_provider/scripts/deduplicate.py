import duckdb
from src.core.db_manager import DatabaseManager
import os

db_path = os.path.join("data", "yfinance.duckdb")

if not os.path.exists(db_path):
    print("Database not found, no deduplication needed.")
    exit(0)

print(f"Connecting to {db_path}...")
conn = duckdb.connect(db_path)

tables = ["financials", "balance_sheet", "cashflow"]

for table in tables:
    print(f"Deduplicating {table}...")
    try:
        # Step 1: Create a temporary table with the latest unique entries
        conn.execute(f"""
            CREATE OR REPLACE TABLE {table}_temp AS
            SELECT ticker, date, item, value, period_type, updated_at
            FROM (
                SELECT *, row_number() OVER (PARTITION BY ticker, date, item, period_type ORDER BY updated_at DESC) as rn
                FROM {table}
            ) WHERE rn = 1;
        """)
        
        # Step 2: Drop the original table
        conn.execute(f"DROP TABLE {table};")
        print(f"Dropped original {table}.")
    except Exception as e:
        print(f"Error deduplicating {table}: {e}")

try:
    print("Deduplicating prices...")
    conn.execute("""
        CREATE OR REPLACE TABLE prices_temp AS
        SELECT ticker, date, open, high, low, close, volume, dividends, stock_splits, updated_at
        FROM (
            SELECT *, row_number() OVER (PARTITION BY ticker, date ORDER BY updated_at DESC) as rn
            FROM prices
        ) WHERE rn = 1;
    """)
    conn.execute("DROP TABLE prices;")
    print("Dropped original prices.")
except Exception as e:
    print(f"Error deduplicating prices: {e}")

conn.close()

# Step 3: Re-initialize the schema using DatabaseManager (this will recreate tables with UNIQUE constraints)
print("Re-initializing database schema with UNIQUE constraints...")
db = DatabaseManager(db_path)
conn = db.get_connection()

# Step 4: Insert the deduplicated data back into the original tables
for table in tables:
    print(f"Restoring {table}...")
    try:
        conn.execute(f"""
            INSERT INTO {table} (ticker, date, item, value, period_type, updated_at)
            SELECT ticker, date, item, value, period_type, updated_at FROM {table}_temp;
        """)
        conn.execute(f"DROP TABLE {table}_temp;")
    except Exception as e:
        print(f"Error restoring {table}: {e}")

try:
    print("Restoring prices...")
    conn.execute("""
        INSERT INTO prices (ticker, date, open, high, low, close, volume, dividends, stock_splits, updated_at)
        SELECT ticker, date, open, high, low, close, volume, dividends, stock_splits, updated_at FROM prices_temp;
    """)
    conn.execute("DROP TABLE prices_temp;")
except Exception as e:
    print(f"Error restoring prices: {e}")

conn.close()
print("Deduplication and schema update complete.")
