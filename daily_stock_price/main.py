import argparse
import logging
import sys

import duckdb

from src.engine import MarketDataEngine
from src.fetchers.yf_fetcher import YFinanceFetcher
from src.universe import UniverseManager

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def check_api_health(port: int) -> str:
    """
    APIの状態を確認する。
    'running': 自システムのAPIが稼働中
    'blocked': 他のサービスがポートを使用中
    'free': ポートは空いている
    """
    import requests

    try:
        response = requests.get(f"http://127.0.0.1:{port}/", timeout=1)
        if response.status_code == 200:
            data = response.json()
            if "Daily Stock Price API" in str(data.get("message", "")):
                return "running"
            return "blocked"
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return "free"
    except Exception:
        return "blocked"
    return "free"


def main():
    logger.info("Starting Daily Stock Price DB synchronization tool")
    parser = argparse.ArgumentParser(
        description="Daily Stock Price DB - High Compression & Incremental Sync"
    )
    parser.add_argument("--sync", nargs="+", help="Tickers to sync (US: AAPL, JP: 7203.T)")
    parser.add_argument(
        "--sync-market", choices=["us", "jp", "all"], help="Sync entire US or JP market"
    )
    parser.add_argument(
        "--workers", type=int, default=5, help="Number of parallel workers for market sync"
    )
    parser.add_argument(
        "--days", type=int, help="Number of days to sync (overrides incremental max_date)"
    )
    parser.add_argument("--view", type=str, help="Ticker to view cleaned data for")
    parser.add_argument(
        "--sql", type=str, help="Custom SQL against the DB (Use '{T}' for ticker view)"
    )
    parser.add_argument("--api", action="store_true", help="Start the FastAPI server")
    parser.add_argument("--port", type=int, default=5005, help="Port for the API server")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host for the API server")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn reload")

    args = parser.parse_args()

    if args.api:
        health = check_api_health(args.port)
        if health == "running":
            logger.info(f"API is already running on port {args.port}. Skipping startup.")
            return
        elif health == "blocked":
            logger.error(
                f"Port {args.port} is occupied by another service. "
                "Please use --port to specify different port."
            )
            sys.exit(1)

        logger.info(f"Starting API server on {args.host}:{args.port} (reload={args.reload})...")
        import uvicorn
        import os

        # Calculate optimal worker count based on CPU cores, leaving buffer for system stability
        cpu_count = os.cpu_count() or 1
        is_windows = sys.platform == "win32"
        
        # Safety formula: Use CPU-2, minimum 1. 
        # Only use multiple workers if reload is False to avoid conflicts.
        if is_windows:
            # Windows handles uvicorn workers poorly with the default spawn method,
            # often leading to OSError: [WinError 10022]. Forcing 1 worker for stability.
            worker_count = 1
        else:
            worker_count = max(1, cpu_count - 2) if not args.reload else 1
        
        if not args.reload:
            if is_windows:
                logger.info(
                    "Concurrency Hardening: Windows detected. Auto-scaling bypassed (Using 1 worker for stability)."
                )
            else:
                logger.info(
                    f"Concurrency Hardening: Auto-scaling enabled. Using {worker_count} workers for CPU cores: {cpu_count}"
                )

        uvicorn.run(
            "src.api.app:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            workers=worker_count if not args.reload else None,
        )
        return

    # 取得ソースの初期化（yfinance専用だが、プラグイン構造でDI）
    fetcher = YFinanceFetcher()
    engine = MarketDataEngine(fetcher=fetcher)

    if args.sync:
        for ticker in args.sync:
            engine.sync_ticker(ticker, lookback_days=args.days)

    if args.sync_market:
        um = UniverseManager()
        tickers = []
        if args.sync_market in ["us", "all"]:
            tickers.extend(um.get_us_universe())
        if args.sync_market in ["jp", "all"]:
            tickers.extend(um.get_jp_universe())

        if tickers:
            engine.sync_tickers(tickers, max_workers=args.workers, lookback_days=args.days)
        else:
            logger.error("No tickers found for the selected market.")

    if args.view:
        sql = engine.get_synced_view(args.view)
        db = duckdb.connect()
        df = db.query(sql).to_df()
        print(f"\n--- Cleaned Data View for {args.view} (Latest Timestamp Filtered) ---")
        print(df.tail(10))

    if args.sql and "{T}" in args.sql:
        # プレースホルダを実際のビューSQLに置換する簡易的なラッパー
        ticker_extract = input("Enter ticker for SQL {T} placeholder: ")
        view_sql = engine.get_synced_view(ticker_extract)
        final_sql = args.sql.replace("{T}", f"({view_sql})")
        db = duckdb.connect()
        print(db.query(final_sql).to_df())


if __name__ == "__main__":
    main()
