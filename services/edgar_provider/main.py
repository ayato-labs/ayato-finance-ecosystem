import argparse
import sys
import time
from loguru import logger
from src.engine import USEngine

def main():
    try:
        parser = argparse.ArgumentParser(description="EDGAR Provider CLI")
        parser.add_argument("--ticker", type=str, help="Sync specific ticker")
        parser.add_argument("--all", action="store_true", help="Sync all companies (sequential)")
        parser.add_argument("--bulk", action="store_true", help="Sync all companies using bulk ZIP (fast)")
        parser.add_argument("--limit", type=int, default=5, help="Limit number of filings to sync")
        parser.add_argument("--api", action="store_true", help="Start API server")
        parser.add_argument("--port", type=int, default=5008)

        args = parser.parse_args()
        engine = USEngine()

        if args.api:
            import uvicorn
            from src.api.server import app
            logger.info(f"Starting EDGAR Provider API on port {args.port}")
            uvicorn.run(app, host="0.0.0.0", port=args.port)
            return

        session_id = f"edgar-sync-{int(time.time())}"

        if args.bulk:
            logger.info("Syncing all US tickers using bulk data...")
            engine.ingest_bulk_data(session_id)
            logger.info("Bulk sync completed.")
        elif args.all:
            logger.info("Syncing all US tickers sequentially...")
            engine.ingest_all_companies(session_id)
            logger.info("Sync completed.")
        elif args.ticker:
            logger.info(f"Syncing US Ticker {args.ticker}...")
            engine.fetch_and_ingest_company(args.ticker, session_id, limit=args.limit)
            logger.info("Done.")
        else:
            parser.print_help()
    except BaseException as e:
        logger.critical(f"FATAL: Process exited due to {type(e).__name__}: {e}")
        import traceback
        logger.critical(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
