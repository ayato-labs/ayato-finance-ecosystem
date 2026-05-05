import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pyarrow.parquet as pq

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))
from src.catalog import CatalogManager

LOG_INTERVAL = 1000
FLUSH_THRESHOLD = 100000


def rebuild():
    catalog = CatalogManager()
    print("Clearing existing catalog...")
    catalog.clear()

    def process_file(file_path: Path, data_type: str):
        try:
            # Only read the Ticker column to be fast
            table = pq.read_table(str(file_path), columns=["Ticker"])
            tickers = table["Ticker"].unique().to_pylist()
            return tickers, str(file_path).replace("\\", "/"), data_type
        except Exception as e:
            # We don't use loguru here to keep tool dependencies minimal, 
            # but we should at least print if something goes wrong.
            # Only print if it's not a common 'column not found' error.
            if "Ticker" not in str(e):
                print(f"  [ERROR] Failed to process {file_path.name}: {e}")
            return None

    def index_files(pattern: str, data_type: str):
        files = list(Path("data").glob(pattern))
        if not files:
            print(f"No files found for {data_type}")
            return

        print(f"Indexing {len(files)} files for {data_type} using parallel pyarrow workers...")
        start_all = time.time()

        # Using a thread pool to speed up the 55k file scan
        all_mappings = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_file = {executor.submit(process_file, f, data_type): f for f in files}

            completed = 0
            for future in as_completed(future_to_file):
                result = future.result()
                if result:
                    tickers, path, dtype = result
                    for t in tickers:
                        all_mappings.append((t, path, dtype))

                completed += 1
                if completed % LOG_INTERVAL == 0:
                    print(
                        f"  Scanned {completed}/{len(files)} files... "
                        f"({len(all_mappings)} mappings)"
                    )

                # Periodically flush to DB to keep memory usage low
                if len(all_mappings) > FLUSH_THRESHOLD:
                    catalog.register_many(all_mappings)
                    all_mappings = []

        # Final flush
        if all_mappings:
            catalog.register_many(all_mappings)

        print(f"Finished {data_type} indexing in {time.time() - start_all:.2f}s")

    # 1. Price Data
    index_files("market_data/**/*.parquet", "price")

    print("\nRebuild complete!")


if __name__ == "__main__":
    rebuild()
