import argparse
import sys

import uvicorn
from dotenv import load_dotenv
from loguru import logger

# .env ファイルの読み込み
load_dotenv()

from src.api.app import app, engine, fetcher

# Configure loguru
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add("data/forex_error.log", level="ERROR", rotation="10 MB")
logger.add("data/forex.log", level="INFO", rotation="10 MB")


def run_sync(symbol: str):
    """
    為替データの同期を実行する。
    """
    logger.info(f"Starting forex sync for {symbol}...")
    last_date = engine.get_latest_date(symbol)
    df = fetcher.fetch(symbol, last_date)

    if df.empty:
        logger.info(f"No new forex data to sync for {symbol}.")
        return

    engine.save_data(symbol, df)
    logger.info(f"Forex sync completed for {symbol}.")


def main():
    parser = argparse.ArgumentParser(description="Forex Service")
    parser.add_argument("command", choices=["sync", "server"], help="Command to run")
    parser.add_argument("--symbol", help="Currency symbol (e.g., JPY, EUR, CNY)")
    parser.add_argument("--port", type=int, default=5011, help="Server port (default: 5011)")

    args = parser.parse_args()

    if args.command == "sync":
        if args.symbol:
            run_sync(args.symbol.upper())
        else:
            # 主要通貨をデフォルトで同期
            for s in ["JPY", "EUR", "CNY"]:
                run_sync(s)
    elif args.command == "server":
        logger.info(f"Starting forex server on port {args.port}...")
        uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
