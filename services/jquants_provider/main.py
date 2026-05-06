import argparse
import datetime
import sys
import time

from loguru import logger

from src.core.logging import setup_logging
from src.engine import JPEngine


def main():
    setup_logging()
    session_id = str(int(time.time()))
    logger.info(f"--- J-Quants Provider Session Started (ID: {session_id}) ---")

    try:
        parser = argparse.ArgumentParser(description="J-Quants Data Provider")
        parser.add_argument("--sync-tickers", action="store_true", help="Sync ticker master")
        parser.add_argument("--sync-prices", action="store_true", help="Sync daily prices")
        parser.add_argument(
            "--sync-market", action="store_true", help="Sync market/financial facts"
        )
        parser.add_argument("--sync-dividends", action="store_true", help="Sync dividends")
        parser.add_argument("--sync-indices", action="store_true", help="Sync indices")
        parser.add_argument(
            "--limit", type=int, help="Limit number of days to sync if no data exists"
        )
        parser.add_argument("--api", action="store_true", help="Start API server")
        parser.add_argument(
            "--optimize", action="store_true", help="Run database maintenance (VACUUM)"
        )
        parser.add_argument("--port", type=int, default=5007)

        args = parser.parse_args()

        if args.api:
            import uvicorn
            from src.api.server import app

            logger.info(f"Starting API server on port {args.port}...")
            uvicorn.run(app, host="0.0.0.0", port=args.port)
            return

        engine = JPEngine()

        if args.sync_tickers:
            logger.info("--- Phase: Ticker Sync ---")
            engine.sync_tickers()

        if args.sync_prices:
            logger.info("--- Phase: Price Sync ---")
            sync_range = args.limit or 365
            end_date = datetime.date.today()
            target_start = end_date - datetime.timedelta(days=sync_range)

            db_latest = engine.get_latest_price_date()
            db_earliest = engine.get_earliest_price_date()

            if not db_latest:
                start_date = target_start
                logger.info(
                    f"No existing data. Starting from scratch "
                    f"({sync_range} days back: {start_date})."
                )
            else:
                latest_dt = datetime.datetime.strptime(db_latest, "%Y%m%d").date()
                earliest_dt = datetime.datetime.strptime(db_earliest, "%Y%m%d").date()

                if latest_dt < end_date:
                    start_date = latest_dt + datetime.timedelta(days=1)
                    logger.info(f"Incremental sync: {start_date} to {end_date}")
                elif earliest_dt > target_start:
                    start_date = target_start
                    end_date = earliest_dt - datetime.timedelta(days=1)
                    logger.info(
                        f"Backfilling history: {start_date} to {end_date} "
                        f"(Requested limit: {sync_range} days)."
                    )
                else:
                    logger.info(
                        f"Database range ({db_earliest} to {db_latest}) "
                        f"covers requested limit ({sync_range} days)."
                    )
                    start_date = end_date + datetime.timedelta(days=1)  # Trigger "up to date"

            if start_date > end_date:
                logger.info("Prices are already up to date for the requested range.")
            else:
                logger.info(f"Initiating price sync: {start_date} -> {end_date}")
                try:
                    df = engine.fetch_prices_range(
                        start_date.strftime("%Y%m%d"),
                        end_date.strftime("%Y%m%d"),
                        session_id=session_id,
                    )
                    if df is not None and not df.empty:
                        engine.ingest_prices(df, session_id)
                        logger.info("Successfully finished price sync phase.")
                    else:
                        logger.warning("No price data was returned for the requested period.")
                except Exception as e:
                    logger.error(f"Critical failure in price sync phase: {e}")
                    raise

        if args.sync_market:
            logger.info("--- Phase: Financial Sync ---")
            sync_range = args.limit or 730
            end_date = datetime.date.today()
            target_start = end_date - datetime.timedelta(days=sync_range)

            db_latest = engine.get_latest_facts_date()
            db_earliest = engine.get_earliest_facts_date()

            if not db_latest:
                start_date = target_start
                logger.info(
                    f"No existing financials. Starting from scratch "
                    f"({sync_range} days back: {start_date})."
                )
            else:
                latest_dt = datetime.datetime.strptime(db_latest, "%Y%m%d").date()
                earliest_dt = datetime.datetime.strptime(db_earliest, "%Y%m%d").date()

                if latest_dt < end_date:
                    start_date = latest_dt + datetime.timedelta(days=1)
                    logger.info(f"Incremental financial sync: {start_date} to {end_date}")
                elif earliest_dt > target_start:
                    start_date = target_start
                    end_date = earliest_dt - datetime.timedelta(days=1)
                    logger.info(
                        f"Backfilling financial history: {start_date} to {end_date} "
                        f"(Requested limit: {sync_range} days)."
                    )
                else:
                    logger.info(
                        f"Database range ({db_earliest} to {db_latest}) "
                        f"covers requested financials limit ({sync_range} days)."
                    )
                    start_date = end_date + datetime.timedelta(days=1)

            if start_date > end_date:
                logger.info("Financials are already up to date for the requested range.")
            else:
                logger.info(f"Initiating financial sync: {start_date} -> {end_date}")
                try:
                    df = engine.fetch_fin_range(
                        start_date.strftime("%Y%m%d"),
                        end_date.strftime("%Y%m%d"),
                        session_id=session_id,
                    )
                    if df is not None and not df.empty:
                        engine.ingest_facts(df, session_id)
                        logger.info("Successfully finished financial sync phase.")
                    else:
                        logger.warning("No financial data was returned for the requested period.")
                except Exception as e:
                    logger.error(f"Critical failure in financial sync phase: {e}")
                    raise

        if args.optimize:
            logger.info("--- Phase: Storage Optimization ---")
            engine.optimize_storage()

        logger.info("J-Quants Provider session completed successfully.")

    except Exception as e:
        logger.critical(f"Fatal error during execution: {e}")
        sys.exit(1)

    # (Indices and Dividends follow similar patterns but restricted on most plans)


if __name__ == "__main__":
    main()
