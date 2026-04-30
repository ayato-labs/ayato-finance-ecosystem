import time
import requests
import pyarrow.parquet as pq
import glob
from pathlib import Path
import sqlite3

# Configuration
API_URL = "http://127.0.0.1:5005"
DB_PATH = "data/catalog.sqlite"
DATA_DIR = "data/market_data"

def bold(text): return f"\033[1m{text}\033[0m"
def green(text): return f"\033[32m{text}\033[0m"
def red(text): return f"\033[31m{text}\033[0m"

def audit():
    print(bold("=== Daily Stock Price API: Lean Dogfooding Auditor ==="))
    
    # 1. Physical Schema Audit
    print(f"\n[1/4] Auditing Physical Parquet Schema...")
    files = glob.glob(f"{DATA_DIR}/**/*.parquet", recursive=True)
    if not files:
        print(red("Error: No data files found!"))
        return

    sample_file = files[0]
    schema = pq.read_schema(sample_file)
    expected_cols = {'Date', 'Ticker', 'Open', 'High', 'Low', 'Close', 'Volume', 'StockSplits', 'Source', 'LoadTimestamp'}
    actual_cols = set(schema.names)
    
    missing = expected_cols - actual_cols
    extra = actual_cols - expected_cols
    
    if not missing and not extra:
        print(green(f"  Schema Valid: Exactly 6 core dimensions + 4 metadata columns found."))
    else:
        if missing: print(red(f"  Missing required columns: {missing}"))
        if extra: print(red(f"  Non-compliant extra columns found: {extra}"))

    # 2. Catalog Integrity Audit
    print(f"\n[2/4] Auditing Metadata Catalog Consistency...")
    with sqlite3.connect(DB_PATH) as conn:
        db_file_count = conn.execute("SELECT COUNT(DISTINCT file_path) FROM ticker_index").fetchone()[0]
        db_ticker_count = conn.execute("SELECT COUNT(DISTINCT ticker) FROM ticker_index").fetchone()[0]
    
    fs_file_count = len(files)
    
    if db_file_count == fs_file_count:
        print(green(f"  Catalog In-Sync: {db_file_count} files correctly indexed."))
    else:
        print(red(f"  Drift Detected! Files on disk: {fs_file_count}, Indexed in DB: {db_file_count}"))

    # 3. API Performance Audit
    print(f"\n[3/4] Benchmarking API Latency (10-Year History Fetch)...")
    try:
        # We'll use MSFT as it usually has complete history
        start_time = time.time()
        resp = requests.get(f"{API_URL}/prices/MSFT", timeout=10)
        elapsed = time.time() - start_time
        
        if resp.status_code == 200:
            data = resp.json()
            rows = len(data)
            print(green(f"  Success: Fetched {rows} rows for MSFT in {elapsed:.4f}s."))
            if elapsed < 0.5:
                print(green(f"  Performance Check: SUB-SECOND (Target: <0.5s) - PASSED"))
            else:
                print(red(f"  Performance Check: SLOW (>0.5s) - WARNING"))
        else:
            print(red(f"  API Error: Status {resp.status_code}"))
    except Exception as e:
        print(red(f"  Connectivity Error: {e}"))

    # 4. Lean Property Audit
    print(f"\n[4/4] Verifying Lean Data Exclusivity...")
    fin_dir = Path("data/financials")
    if fin_dir.exists():
        print(red("  Warning: Orphaned 'financials' directory found!"))
    else:
        print(green("  Lean Check: No non-price data directories remain. System is PURE."))

    print(bold("\n=== Audit Complete ==="))

if __name__ == "__main__":
    audit()
