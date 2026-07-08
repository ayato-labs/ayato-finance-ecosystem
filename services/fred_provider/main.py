import argparse

from dotenv import load_dotenv
from loguru import logger
from src.core.logging import setup_logger

# .env ファイルの読み込み(インポートより前に行う)
load_dotenv()

from src.engine import MacroEngine
from src.fetchers.fred_fetcher import FredFetcher

engine = MacroEngine()
fetcher = FredFetcher()

# Configure structured logging
setup_logger(log_dir="logs", app_name="fred_provider")


def run_sync(symbol: str):
    """
    データの同期を実行する。
    """
    logger.info(f"Starting sync for {symbol}...")
    last_date = engine.get_latest_date(symbol)
    df = fetcher.fetch(symbol, last_date)

    if df.empty:
        logger.info(f"No new data to sync for {symbol}.")
        return

    engine.save_data(symbol, df)
    logger.info(f"Sync completed for {symbol}.")


def main():
    parser = argparse.ArgumentParser(description="FRED Provider Service")
    parser.add_argument("--symbol", help="Indicator symbol (e.g., DFF, DGS10)")

    args = parser.parse_args()

    if args.symbol:
        run_sync(args.symbol)
    else:
        # MVP: 政策金利と10年債利回りをデフォルトで同期
        for s in ["DFF", "DGS10"]:
            run_sync(s)


if __name__ == "__main__":
    main()
