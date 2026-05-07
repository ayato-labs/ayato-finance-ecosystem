import argparse
import sys
from dotenv import load_dotenv
from src.core.logging_config import setup_logging
from src.ingestion.collector import FredCollector
from src.ingestion.writer import FredWriter
from loguru import logger
import threading

load_dotenv()

def run_sync(symbols: list[str]):
    setup_logging()
    logger.info("Starting synchronization process.")
    
    collector = FredCollector()
    writer = FredWriter("data/fred.duckdb")
    
    # Writerを別スレッドで起動
    writer_thread = threading.Thread(target=writer.write_loop, args=(collector.data_queue,))
    writer_thread.start()
    
    # 取得開始
    collector.run(symbols, "2024-01-01")
    
    # 終了待ち
    writer_thread.join()
    logger.info("Synchronization completed.")

def main():
    parser = argparse.ArgumentParser(description="FRED Provider CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    sync_parser = subparsers.add_parser("sync")
    sync_parser.add_argument("--symbols", nargs="+", default=["DFF", "UNRATE"])
    
    args = parser.parse_args()
    
    if args.command == "sync":
        run_sync(args.symbols)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
