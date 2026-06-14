import argparse
import json
import os

from loguru import logger
from ..core.config import get_db_path, get_universe_cache_dir
from ..core.db_manager import DatabaseManager
from ..core.logging import setup_logger
from .engine import SyncEngine
from ..universe.manager import UniverseManager

setup_logger(log_dir="logs", app_name="yfinance_collector")


def main():
    parser = argparse.ArgumentParser(description="yfinance Collector CLI")
    parser.add_argument("--tickers", type=str, help="Comma separated tickers")
    parser.add_argument(
        "--sync-market", choices=["us", "jp", "all"], help="Sync entire US or JP market"
    )
    parser.add_argument("--force", action="store_true", help="Force sync")
    parser.add_argument("--workers", type=int, default=4, help="Max parallel workers")

    args = parser.parse_args()

    db_path = get_db_path()
    db_manager = DatabaseManager(db_path)
    engine = SyncEngine(db_manager, max_workers=args.workers)

    tickers = []
    if args.tickers:
        tickers = [t.strip() for t in args.tickers.split(",")]
    elif args.sync_market:
        um = UniverseManager(cache_dir=get_universe_cache_dir())
        if args.sync_market in ["us", "all"]:
            tickers.extend(um.get_us_universe())
        if args.sync_market in ["jp", "all"]:
            tickers.extend(um.get_jp_universe())
        logger.info(f"Discovered {len(tickers)} tickers for market {args.sync_market}")
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

    if not tickers:
        logger.warning("No tickers to sync.")
        return

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
