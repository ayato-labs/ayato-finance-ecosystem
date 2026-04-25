import argparse
import logging
import uvicorn
import coloredlogs
from dotenv import load_dotenv

# .env ファイルの読み込み（インポートより前に行う）
load_dotenv()

from src.api.app import app, engine, fetcher

# ログ設定
coloredlogs.install(level='INFO', fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
    parser = argparse.ArgumentParser(description="Macro Economic Service")
    parser.add_argument("command", choices=["sync", "server"], help="Command to run")
    parser.add_argument("--symbol", help="Indicator symbol (e.g., DFF, DGS10)")
    parser.add_argument("--port", type=int, default=5010, help="Server port (default: 5010)")
    
    args = parser.parse_args()

    if args.command == "sync":
        if args.symbol:
            run_sync(args.symbol)
        else:
            # MVP: 政策金利と10年債利回りをデフォルトで同期
            for s in ["DFF", "DGS10"]:
                run_sync(s)
    elif args.command == "server":
        logger.info(f"Starting server on port {args.port}...")
        uvicorn.run(app, host="127.0.0.1", port=args.port)

if __name__ == "__main__":
    main()
