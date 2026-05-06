import sqlite3
from pathlib import Path
import os

# Define paths
base_path = Path("c:/Users/saiha/My_Service/programing/finance/services/daily_stock_price")
db_path = base_path / "data" / "catalog.sqlite"

def analyze_catalog():
    print(f"--- Catalog Analysis (SQLite) ---", flush=True)
    if not db_path.exists():
        print(f"Catalog file not found at {db_path}", flush=True)
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    unique_tickers = cursor.execute("SELECT COUNT(DISTINCT ticker) FROM ticker_index").fetchone()[0]
    total_mappings = cursor.execute("SELECT COUNT(*) FROM ticker_index").fetchone()[0]
    
    # Get breakdown by ticker suffix (market)
    # .T is Japan, others usually US
    jp_tickers = cursor.execute("SELECT COUNT(DISTINCT ticker) FROM ticker_index WHERE ticker LIKE '%.T'").fetchone()[0]
    us_tickers = unique_tickers - jp_tickers
    
    print(f"Total Unique Tickers: {unique_tickers}", flush=True)
    print(f"  - Japanese Tickers (.T): {jp_tickers}", flush=True)
    print(f"  - US Tickers (Other): {us_tickers}", flush=True)
    print(f"Total Ticker-File Mappings: {total_mappings}", flush=True)
    
    conn.close()

def analyze_files():
    print(f"\n--- File System Analysis ---", flush=True)
    data_dir = base_path / "data" / "market_data"
    years = sorted([d.name for d in data_dir.glob("year=*")])
    if years:
        print(f"Data spans from {years[0]} to {years[-1]}", flush=True)
        print(f"Total years with data: {len(years)}", flush=True)
    else:
        print("No year directories found.", flush=True)

if __name__ == "__main__":
    analyze_catalog()
    analyze_files()
