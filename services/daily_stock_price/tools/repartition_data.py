import shutil
from pathlib import Path

import duckdb

from src.engine import MarketDataEngine
from src.fetchers.yf_fetcher import YFinanceFetcher


def migrate():
    base_dir = Path("./data/market_data")
    backup_dir = Path("./data/market_data_backup")

    if not base_dir.exists():
        print("No market data found.")
        return

    print(f"Starting migration of partitions in {base_dir}...")

    # 1. Backup existing data
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    shutil.copytree(base_dir, backup_dir)
    print(f"Backup created at {backup_dir}")

    # 2. Load ALL data using DuckDB (to handle different partitions seamlessly)
    db = duckdb.connect()
    all_data_df = db.query(f"SELECT * FROM read_parquet('{base_dir}/**/*.parquet')").to_df()
    print(f"Loaded {len(all_data_df)} records for re-partitioning.")

    # 3. Clear original directory (keep only root)
    for item in base_dir.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    # 4. Use the NEW partitioning logic to save
    # (Initialize engine just to use its save_parquet method)
    fetcher = YFinanceFetcher()
    engine = MarketDataEngine(fetcher=fetcher, base_dir=str(base_dir))

    # save_parquet already handles grouping by year/month
    engine.save_parquet(all_data_df)

    print("Migration complete. Verifying structure...")
    for p in base_dir.glob("**/*.parquet"):
        print(f"  [OK] {p.relative_to(base_dir)}")


if __name__ == "__main__":
    migrate()
