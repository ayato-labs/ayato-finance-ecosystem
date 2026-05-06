import argparse
import asyncio
import sys

import uvicorn
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

from src.batch_fetch import batch_fetch
from src.config import DEFAULT_PORT
from src.logging_utils import setup_logging
from src.storage import FinancialNarrativeStorage

# 初期化
setup_logging("financial_narratives")


def run_diagnostics():
    """DuckDB内のデータ状況を診断・表示する"""
    try:
        storage = FinancialNarrativeStorage()
        summary = storage.get_summary()

        if not summary:
            logger.warning("DuckDB is currently empty")
            return

        logger.info("--- Database Diagnostics ---")
        for row in summary:
            logger.info(f"Ticker: {row[0]:<6} | Form: {row[1]:<6} | Date: {row[2]}")
    except Exception:
        logger.exception("Failed to run diagnostics")


def main():
    parser = argparse.ArgumentParser(
        description="Financial Narratives - SEC/EDINET Qualitative Data Service"
    )
    parser.add_argument("--sync", nargs="*", help="Tickers to sync (empty for default list)")
    parser.add_argument(
        "--days", type=int, default=1825, help="Days to look back for automated sync"
    )
    parser.add_argument(
        "--reconcile",
        action="store_true",
        help="Run the reconciler to find un-structured documents",
    )
    parser.add_argument("--work", action="store_true", help="Start the structuring worker pool")
    parser.add_argument("--workers", type=int, default=10, help="Number of concurrent LLM workers")
    parser.add_argument("--diag", action="store_true", help="Run database diagnostics")
    parser.add_argument("--api", action="store_true", help="Start the FastAPI server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port for the API server")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host for the API server")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn reload")
    parser.add_argument("--market", type=str, default=None, help="Target market (jp/us)")

    args = parser.parse_args()

    try:
        if args.api:
            logger.info(f"Starting API server | market={args.market} | port={args.port}")
            # APIサーバー側でも市場を意識できるように環境変数などにセットする
            if args.market:
                os.environ["FINANCIAL_NARRATIVE_MARKET"] = args.market
            uvicorn.run("src.api.app:app", host=args.host, port=args.port, reload=args.reload)
            return

        if args.sync is not None:
            tickers = args.sync if args.sync else None
            logger.info(
                f"Starting batch fetch task (Ingestion) | tickers={tickers} | days={args.days}"
            )
            asyncio.run(batch_fetch(market=args.market, tickers=tickers, days=args.days))
            run_diagnostics()
            return

        if args.reconcile:
            from src.reconciler import Reconciler

            market = args.market or "all"
            logger.info(f"Starting Reconciler for {market}...")
            reconciler = Reconciler(market=args.market)
            reconciler.run(market=args.market)
            return

        if args.work:
            from src.structuring_worker import StructuringWorkerPool

            logger.info(f"Starting Worker Pool with {args.workers} workers...")
            pool = StructuringWorkerPool(num_workers=args.workers)
            asyncio.run(pool.run_forever())
            return

        if args.diag:
            run_diagnostics()
            return

        # Default: Show help
        parser.print_help()

    except Exception:
        logger.exception("Critical failure in main execution loop")
        sys.exit(1)


if __name__ == "__main__":
    main()
