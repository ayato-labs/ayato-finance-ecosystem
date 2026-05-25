import argparse
import logging as std_logging
import os
import sys

import httpx
import uvicorn
from loguru import logger
from src.core.logging import setup_logger

from src.core.config import settings
from src.edinet.sync_worker import EDINETSyncWorker
from src.services.market_sync import BatchSyncService

# Constants
HTTP_OK = 200

# Configure structured logging
setup_logger(log_dir="logs", app_name="financial_figures")

# Silence noisy libraries
std_logging.getLogger("httpx").setLevel(std_logging.WARNING)


def check_api_health(port: int) -> str:
    """
    Check API status.
    'running': This system is already alive.
    'blocked': Another process is using the port.
    'free': Port is available.
    """
    try:
        with httpx.Client(timeout=1.0) as client:
            response = client.get(f"http://127.0.0.1:{port}/health")
            if response.status_code == HTTP_OK:
                data = response.json()
                if data.get("status") == "healthy":
                    return "running"
            return "blocked"
    except (httpx.ConnectError, httpx.TimeoutException):
        return "free"
    except Exception:
        return "blocked"


def run_api_server(args):
    """Handles API server startup logic."""
    health = check_api_health(args.port)
    if health == "running":
        logger.info(f"API is already running on port {args.port}. Skipping startup.")
        return
    elif health == "blocked":
        logger.error(
            f"Port {args.port} is blocked by another service. Please choose a different port."
        )
        sys.exit(1)

    if args.no_sync:
        os.environ["DISABLE_AUTO_SYNC"] = "true"
    if args.read_only:
        os.environ["DB_READ_ONLY"] = "true"

    logger.info(f"Starting Unified API Server on {args.host}:{args.port} (reload={args.reload})...")

    worker_count = 1
    logger.info(f"Using {worker_count} worker (DuckDB requires a single process lock).")

    uvicorn.run(
        "src.api.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=worker_count if not args.reload else None,
    )


def perform_individual_sync(sync_service, args):
    """Sync specific tickers."""
    logger.info(f"Starting individual sync for: {args.sync}")
    ticker_code_len_jp = 4
    for ticker in args.sync:
        if ticker.isdigit() and len(ticker) == ticker_code_len_jp:
            df = sync_service.jp_engine.fetch_statements(ticker)
            if df is not None and not df.empty:
                logger.info(f"Adding JP ticker {ticker} to sync queue.")
                sync_service.db_queue.put(("JP_INGEST", ticker, df, args.session))
            else:
                sync_service.db_queue.put(("LOG_SKIP", "JP", ticker, "EMPTY_RESULT"))
        else:
            data = sync_service.us_engine.fetch_company_facts(ticker)
            if data:
                logger.info(f"Adding US ticker {ticker} to sync queue.")
                sync_service.db_queue.put(("US_INGEST", ticker, data, args.session))
            else:
                sync_service.db_queue.put(("LOG_SKIP", "US", ticker, "404 NOT_FOUND"))
    sync_service.wait_for_queues()
    logger.info("Individual sync completed.")


def perform_market_sync(sync_service, args):
    """Sync specific markets."""
    market_choice = args.sync_market.lower()
    limit = args.limit
    dry_run = args.dry_run

    if market_choice in ["us", "all"]:
        logger.info(
            f"=== Starting US Market Sync (Limit: {limit or 'None'}, Incr: {args.incremental}) ==="
        )
        sync_service.sync_market_full(
            "US", limit=limit, dry_run=dry_run, incremental=args.incremental
        )

    if market_choice in ["jp", "all"]:
        logger.info(
            f"=== Starting JP Market Sync (Limit: {limit or 'None'}, Incr: {args.incremental}) ==="
        )
        sync_service.sync_market_full(
            "JP", limit=limit, dry_run=dry_run, incremental=args.incremental
        )
        logger.info("=== Starting EDINET Statutory Sync (Incremental) ===")
        try:
            edinet_worker = EDINETSyncWorker()
            edinet_worker.run_incremental_sync()
        except Exception as e:
            logger.error(f"EDINET Sync failed: {e}")

    logger.info(f"{market_choice.upper()} market sync completed.")


def main():
    parser = argparse.ArgumentParser(
        description="Financial Figures Unified CLI - Automated Sync & Standardized API"
    )

    # API Server Group
    api_group = parser.add_argument_group("API Server")
    api_group.add_argument("--api", action="store_true", help="Start the FastAPI server")
    api_group.add_argument(
        "--port",
        type=int,
        default=settings.API_PORT,
        help=f"Port for the API server (default: {settings.API_PORT})",
    )
    api_group.add_argument("--host", type=str, default="127.0.0.1", help="Host for the API server")
    api_group.add_argument("--reload", action="store_true", help="Enable uvicorn auto-reload")
    api_group.add_argument(
        "--no-sync", action="store_true", help="Disable automatic background sync on API startup"
    )
    api_group.add_argument(
        "--read-only",
        action="store_true",
        help="Open databases in READ_ONLY mode (recommended for viewer-only sessions)",
    )

    # Sync Group
    sync_group = parser.add_argument_group("Market Synchronization")
    sync_group.add_argument(
        "--sync", nargs="+", help="Specific ticker(s) to sync (e.g. --sync AAPL NVDA)"
    )
    sync_group.add_argument(
        "--sync-market", choices=["us", "jp", "all"], help="Sync entire markets"
    )
    sync_group.add_argument(
        "--workers", type=int, help="Number of parallel workers for sync (default: CPU cores - 2)"
    )
    sync_group.add_argument(
        "--limit", type=int, help="Limit the number of tickers to sync per market"
    )
    sync_group.add_argument(
        "--session", type=str, default="cli-session", help="Custom session ID for this sync"
    )
    sync_group.add_argument(
        "--dry-run", action="store_true", help="Simulate sync without downloading facts"
    )
    sync_group.add_argument(
        "--incremental",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Only sync data for tickers that haven't been updated recently (default: True)",
    )
    sync_group.add_argument(
        "--edinet-only", action="store_true", help="Sync only EDINET statutory data"
    )
    sync_group.add_argument(
        "--edinet-backfill",
        nargs="?",
        const="AUTO",
        help=(
            "Run full EDINET historical backfill. "
            "If path is omitted, downloads latest master from EDINET API."
        ),
    )

    args = parser.parse_args()

    # 1. API Server Startup
    if args.api:
        run_api_server(args)
        return

    # 2. Market Synchronization
    try:
        sync_service = BatchSyncService()

        if args.sync:
            perform_individual_sync(sync_service, args)

        if args.edinet_only:
            logger.info("=== Starting EDINET Statutory Sync (Manual/Only Mode) ===")
            worker = EDINETSyncWorker()
            worker.run_incremental_sync()

        if args.sync_market:
            perform_market_sync(sync_service, args)

        if args.edinet_backfill:
            worker = EDINETSyncWorker()
            csv_path = None if args.edinet_backfill == "AUTO" else args.edinet_backfill
            logger.info(f"=== Starting Full EDINET Backfill (Source: {csv_path or 'AUTO/API'}) ===")
            worker.run_historical_backfill(years=5, csv_path=csv_path)

        sync_service.stop()

        if not any([args.sync, args.sync_market, args.edinet_backfill, args.edinet_only]):
            parser.print_help()
        else:
            logger.info("[Success] Sync process completed.")

    except Exception as e:
        logger.exception(f"Critical failure during execution: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
