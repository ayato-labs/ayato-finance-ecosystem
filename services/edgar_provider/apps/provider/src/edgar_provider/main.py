import argparse
import sys
import time

from edgar_core.logging import setup_logging
from loguru import logger

from edgar_provider.engine import USEngine


def main():
    setup_logging()

    context = {"session_id": f"edgar-sync-{int(time.time())}"}
    logger.info("EDGAR Provider starting...", extra={"context": context})

    try:
        parser = argparse.ArgumentParser(description="EDGAR Provider Ingestion CLI")
        parser.add_argument("--ticker", type=str, help="Sync specific ticker")
        parser.add_argument("--all", action="store_true", help="Sync all companies (sequential)")
        parser.add_argument(
            "--bulk", action="store_true", help="Sync all companies using bulk ZIP (fast)"
        )
        parser.add_argument("--limit", type=int, default=5, help="Limit number of filings to sync")

        args = parser.parse_args()
        engine = USEngine()

        session_id = context["session_id"]

        if args.bulk:
            logger.info("Starting bulk data ingestion...", extra={"context": context})
            engine.ingest_bulk_data(session_id)
        elif args.all:
            logger.info(
                "Starting sequential ingestion for all companies...", extra={"context": context}
            )
            engine.ingest_all_companies(session_id)
        elif args.ticker:
            ticker = args.ticker.upper()
            logger.info(f"Syncing ticker {ticker}...", extra={"context": context, "ticker": ticker})
            engine.fetch_and_ingest_company(ticker, session_id, limit=args.limit)
        else:
            parser.print_help()

        logger.info("Process finished successfully.", extra={"context": context})

    except KeyboardInterrupt:
        logger.warning("Process interrupted by user (Ctrl+C).", extra={"context": context})
        sys.exit(130)
    except Exception as e:
        logger.error(
            f"Process failed with {type(e).__name__}: {str(e)}",
            extra={"context": context, "error_type": type(e).__name__},
        )
        # We don't swallow: we let it exit with error log recorded
        raise


if __name__ == "__main__":
    main()
