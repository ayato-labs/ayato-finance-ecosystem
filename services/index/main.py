import argparse
import sys

from loguru import logger
from src.core.logging import setup_logger

from src.api.app import app, engine, fetcher

# Configure structured logging
setup_logger(log_dir="logs", app_name="index")


def run_sync(ticker: str = "^GSPC"):
    """
    データの同期を実行する。
    """
    logger.info(f"Starting sync for {ticker}...")
    last_date = engine.get_latest_date(ticker)
    df = fetcher.fetch(ticker, last_date)

    if df.empty:
        logger.info("No new data to sync.")
        return

    engine.save_data(ticker, df)
    logger.info("Sync completed.")


def main():
    parser = argparse.ArgumentParser(description="Market Index Service")
    parser.add_argument("command", choices=["sync", "server"], help="Command to run")
    parser.add_argument("--ticker", default="^GSPC", help="Ticker symbol (default: ^GSPC)")
    parser.add_argument("--port", type=int, default=5009, help="Server port (default: 5009)")

    args = parser.parse_args()

    if args.command == "sync":
        run_sync(args.ticker)
    elif args.command == "server":
        import uvicorn
        logger.info(f"Starting server on port {args.port}...")
        uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
