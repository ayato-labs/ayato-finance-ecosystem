import duckdb
from pathlib import Path
from src.core.config import settings

def audit_shard(name, path, table_name):
    print(f"\n=== Auditing {name} Shard: {table_name} ===")
    if not path.exists():
        print(f"FAILED: File not found at {path}")
        return
    
    conn = duckdb.connect(str(path), read_only=True)
    try:
        # 1. Basic Stats
        total = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        print(f"Total Records: {total:,}")
        
        if total == 0:
            print("WARNING: Table is empty!")
            return

        # Determine identity columns based on table
        code_col = "Code"
        date_col = "Date"
        if table_name == "company_facts":
            code_col = "LocalCode"
            date_col = "DisclosedDate"
        elif table_name == "tickers":
            code_col = "code"
            date_col = None

        # 2. Null Checks (Primary Identity)
        null_codes = conn.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {code_col} IS NULL").fetchone()[0]
        print(f"NULL Codes ({code_col}): {null_codes} ({(null_codes/total)*100:.2f}%)")
        
        if date_col:
            null_dates = conn.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {date_col} IS NULL").fetchone()[0]
            print(f"NULL Dates ({date_col}): {null_dates} ({(null_dates/total)*100:.2f}%)")

        # 3. Value Sanity Checks
        cols = [c[0] for c in conn.execute(f"DESCRIBE {table_name}").fetchall()]
        if "Close" in cols:
            neg_prices = conn.execute(f"SELECT COUNT(*) FROM {table_name} WHERE Close <= 0").fetchone()[0]
            max_price = conn.execute(f"SELECT MAX(Close) FROM {table_name}").fetchone()[0]
            print(f"Invalid Prices (<=0): {neg_prices}")
            print(f"Max Price Found: {max_price}")

        # 4. Date Range
        if date_col:
            min_date = conn.execute(f"SELECT MIN({date_col}) FROM {table_name}").fetchone()[0]
            max_date = conn.execute(f"SELECT MAX({date_col}) FROM {table_name}").fetchone()[0]
            print(f"Date Range: {min_date} to {max_date}")

        # 5. Sample Data View
        print("\nSample Data (Last 3 records):")
        order_col = date_col if date_col else code_col
        print(conn.execute(f"SELECT * FROM {table_name} ORDER BY {order_col} DESC LIMIT 3").df().to_string())

    except Exception as e:
        print(f"ERROR during audit: {e}")
    finally:
        conn.close()

def main():
    # Audit Prices
    audit_shard("Prices", settings.JP_PRICES_DB_PATH, "daily_prices")
    
    # Audit Financials
    audit_shard("Financials", settings.JP_FACTS_DB_PATH, "company_facts")
    
    # Audit Master
    audit_shard("Master", settings.JP_MASTER_DB_PATH, "tickers")

if __name__ == "__main__":
    main()
