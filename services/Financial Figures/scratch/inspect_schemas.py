import glob
from pathlib import Path

import duckdb


def inspect_all_schemas():
    base_path = "C:/Users/saiha/My_Service/programing/finance/daily_stock_price/data/market_data/"
    # Find some files from different months/years
    files = glob.glob(f"{base_path}/**/*.parquet", recursive=True)
    print(f"Found {len(files)} parquet files.")

    if not files:
        return

    # Sample a few files from different parts of the tree
    samples = sorted(list(set([files[0], files[len(files) // 2], files[-1]])))

    conn = duckdb.connect(":memory:")
    for f in samples:
        rel_path = Path(f).relative_to(base_path)
        print(f"\n--- Schema for {rel_path} ---")
        try:
            # Check column names
            columns = conn.execute(f"SELECT * FROM '{f}' LIMIT 0").df().columns.tolist()
            print(f"Columns: {columns}")

            # Check for case sensitivity issues
            has_close = "close" in columns
            has_Close = "Close" in columns
            print(f"  - 'close' exists: {has_close}")
            print(f"  - 'Close' exists: {has_Close}")
        except Exception as e:
            print(f"Error inspecting {f}: {e}")


if __name__ == "__main__":
    inspect_all_schemas()
