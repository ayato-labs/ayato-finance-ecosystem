import argparse
import asyncio
import sys

import uvicorn
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

from src.batch_fetch import batch_fetch
from src.storage import FinancialNarrativeStorage
from src.config import DEFAULT_PORT

# Configure loguru
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add("data/narratives_error.log", level="ERROR", rotation="10 MB")
logger.add("data/narratives.log", level="INFO", rotation="10 MB")


def run_diagnostics():
    """DuckDB内のデータ状況を診断・表示する"""
    storage = FinancialNarrativeStorage()
    summary = storage.get_summary()

    if not summary:
        logger.warning("DuckDB is currently empty.")
        return

    print("\n" + "=" * 60)
    print(" FINANCIAL NARRATIVES - DATABASE DIAGNOSTICS")
    print("=" * 60)
    print(f"{'Ticker':<10} | {'Form':<8} | {'Filing Date':<12}")
    print("-" * 60)
    for row in summary:
        print(f"{row[0]:<10} | {row[1]:<8} | {row[2]!s:<12}")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Financial Narratives - SEC Qualitative Data Service"
    )
    parser.add_argument("--sync", nargs="*", help="Tickers to sync (empty for default list)")
    parser.add_argument("--diag", action="store_true", help="Run database diagnostics")
    parser.add_argument("--api", action="store_true", help="Start the FastAPI server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port for the API server")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host for the API server")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn reload")

    args = parser.parse_args()

    if args.api:
        logger.info(f"Starting API server on {args.host}:{args.port}...")
        uvicorn.run("src.api.app:app", host=args.host, port=args.port, reload=args.reload)
        return

    if args.sync is not None:
        logger.info("Starting financial narrative collection process...")
        asyncio.run(batch_fetch(args.sync if args.sync else None))
        run_diagnostics()
        return

    if args.diag:
        run_diagnostics()
        return

    # Default: Show help
    parser.print_help()


if __name__ == "__main__":
    main()
