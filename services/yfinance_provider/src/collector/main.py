import argparse
import json
import os

from ..core.db_manager import DatabaseManager
from ..core.logger import setup_logger
from .engine import SyncEngine

logger = setup_logger("collector_main")


def main():
    parser = argparse.ArgumentParser(description="yfinance Collector CLI")
    parser.add_argument("--tickers", type=str, help="Comma separated tickers")
    parser.add_argument("--force", action="store_true", help="Force sync")
    parser.add_argument("--workers", type=int, default=4, help="Max parallel workers")

    args = parser.parse_args()

    db_path = os.path.join("data", "yfinance.duckdb")
    db_manager = DatabaseManager(db_path)
    engine = SyncEngine(db_manager, max_workers=args.workers)

    if args.tickers:
        tickers = [t.strip() for t in args.tickers.split(",")]
    else:
        # JSONファイルがあれば読み込む、なければデフォルト
        ticker_file = os.path.join("data", "tickers_to_sync.json")
        if os.path.exists(ticker_file):
            with open(ticker_file, "r") as f:
                tickers = json.load(f)
            logger.info(f"Loaded {len(tickers)} tickers from {ticker_file}")
        else:
            # デフォルトの銘柄リスト
            tickers = ["AAPL", "MSFT", "GOOGL", "TSLA", "9119.T", "7203.T"]

    engine.run_sync(tickers, force=args.force)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Fatal error in collector main entry point")
        # ユーザーがエラーを確認できるよう、少し待機するかメッセージを出す
        print("\n[FATAL ERROR] Check logs/error.log for details.")
        input("Press Enter to exit...")
        raise
