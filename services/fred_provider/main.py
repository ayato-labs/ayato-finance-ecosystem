import argparse
import sys
from dotenv import load_dotenv
from src.core.logging_config import setup_logging
from src.ingestion.collector import FredCollector
from src.ingestion.writer import FredWriter
from loguru import logger
import threading

load_dotenv()

from src.core.master_db_client import MasterDBClient
import duckdb

def run_sync(symbols: list[str]):
    setup_logging()
    logger.info("Starting synchronization process.")
    
    collector = FredCollector()
    db_path = "data/fred.duckdb"
    writer = FredWriter(db_path)
    
    # ... (previous logic) ...
    writer_thread = threading.Thread(target=writer.write_loop, args=(collector.data_queue,))
    writer_thread.start()
    
    collector.run(symbols, "2024-01-01")
    writer_thread.join()
    
    # Register with Master DB
    conn = duckdb.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    conn.close()
    
    master_client = MasterDBClient()
    master_client.register_provider("fred_provider", db_path, "0.1.0", count)
    
    logger.info("Synchronization completed and registered with Master DB.")

def main():
    parser = argparse.ArgumentParser(description="FRED Provider CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    sync_parser = subparsers.add_parser("sync")
    sync_parser.add_argument("--symbols", nargs="+", default=["DFF", "UNRATE"])
    
    explore_parser = subparsers.add_parser("explore")
    explore_parser.add_argument("--category", type=int, required=True)
    
    args = parser.parse_args()
    
    if args.command == "sync":
        run_sync(args.symbols)
    elif args.command == "explore":
        collector = FredCollector()
        series = collector.discover_series_by_category(args.category)
        print(f"Found {len(series)} series: {series}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
