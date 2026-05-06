import duckdb
import sqlite3
from pathlib import Path
import pandas as pd

# Define paths
base_path = Path("c:/Users/saiha/My_Service/programing/finance/services/daily_stock_price")
db_path = base_path / "data" / "catalog.sqlite"
data_dir = base_path / "data" / "market_data"

def analyze_db():
    print(f"Analyzing database at: {base_path}")
    
    # 1. Catalog Stats (SQLite)
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        unique_tickers = conn.execute("SELECT COUNT(DISTINCT ticker) FROM ticker_index").fetchone()[0]
        total_mappings = conn.execute("SELECT COUNT(*) FROM ticker_index").fetchone()[0]
        conn.close()
        print(f"Catalog Unique Tickers: {unique_tickers}")
        print(f"Catalog Total Mappings: {total_mappings}")
    else:
        print("Catalog SQLite file not found.")

    # 2. Data Stats (DuckDB over Parquet)
    parquet_pattern = str(data_dir / "**" / "*.parquet").replace("\\", "/")
    
    # Check if any parquet files exist
    parquet_files = list(data_dir.glob("**/*.parquet"))
    if not parquet_files:
        print("No Parquet data files found.")
        return

    print(f"Found {len(parquet_files)} Parquet files.")
    
    db = duckdb.connect()
    # Disable optimizer to avoid potential stats corruption issues on some versions
    db.execute("PRAGMA disable_optimizer")
    
    try:
        # Get overall date range and ticker count from actual data
        res = db.query(f"""
            SELECT 
                MIN(Date) as min_date, 
                MAX(Date) as max_date, 
                COUNT(DISTINCT Ticker) as ticker_count,
                COUNT(*) as total_rows
            FROM read_parquet('{parquet_pattern}')
        """).df()
        
        print("\n--- Data Analysis Results ---")
        print(res.to_string(index=False))
        
        # Breakdown by market (Source) if available
        market_res = db.query(f"""
            SELECT 
                Source,
                COUNT(DISTINCT Ticker) as ticker_count,
                MIN(Date) as min_date,
                MAX(Date) as max_date
            FROM read_parquet('{parquet_pattern}')
            GROUP BY Source
        """).df()
        print("\n--- Market Breakdown ---")
        print(market_res.to_string(index=False))

    except Exception as e:
        print(f"Error during DuckDB analysis: {e}")

if __name__ == "__main__":
    analyze_db()
