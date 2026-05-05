import argparse
import datetime
import time
import sys
from loguru import logger
from src.engine import JPEngine
from src.core.logging import setup_logging


def main():
    setup_logging()
    logger.info("J-Quants Provider session started.")
    try:
        parser = argparse.ArgumentParser(description="J-Quants Provider CLI")
        parser.add_argument("--sync-tickers", action="store_true", help="Sync ticker list")
        parser.add_argument(
            "--sync-market", action="store_true", help="Sync entire market financials"
        )
        parser.add_argument("--sync-prices", action="store_true", help="Sync stock prices")
        parser.add_argument("--sync-indices", action="store_true", help="Sync market indices")
        parser.add_argument("--sync-dividends", action="store_true", help="Sync dividend data")
        parser.add_argument("--ticker", type=str, help="Sync specific ticker")
        parser.add_argument(
            "--limit", type=int, help="Limit number of days to sync if no data exists"
        )
        parser.add_argument("--api", action="store_true", help="Start API server")
        parser.add_argument("--port", type=int, default=5007)

        args = parser.parse_args()
        engine = JPEngine()

        if args.api:
            import uvicorn
            from src.api.server import app

            logger.info(f"Starting API server on port {args.port}...")
            uvicorn.run(app, host="127.0.0.1", port=args.port)
            return

        session_id = f"jquants-sync-{int(time.time())}"

        if args.sync_tickers:
            count = engine.sync_tickers(session_id)
            logger.info(f"Synced {count} tickers.")

        if args.ticker:
            logger.info(f"Syncing ticker {args.ticker}...")
            df = engine.fetch_statements(args.ticker)
            engine.ingest_facts(df, session_id)
            logger.info(f"Finished syncing ticker {args.ticker}.")

        if args.sync_prices:
            logger.info("--- Phase: Stock Price Sync ---")
            # J-Quants Free Plan: 12-week (84 days) delay
            delay_days = 84
            end_date = datetime.date.today() - datetime.timedelta(days=delay_days)

            # Target Start Date based on limit
            sync_range = args.limit or 90
            target_start = end_date - datetime.timedelta(days=sync_range)

            # Database Coverage
            db_latest = engine.get_latest_price_date()
            db_earliest = engine.get_earliest_price_date()

            if not db_latest:
                # Case 1: Empty Database
                start_date = target_start
                logger.info(f"No existing data. Starting from scratch ({sync_range} days back: {start_date}).")
            else:
                # Case 2: Fill Future
                latest_dt = datetime.datetime.strptime(db_latest, "%Y%m%d").date()
                if latest_dt < end_date:
                    start_date = latest_dt + datetime.timedelta(days=1)
                    logger.info(f"Existing data found up to {db_latest}. Syncing up to {end_date}.")
                # Case 3: Fill Past (If limit is deeper than earliest)
                elif db_earliest:
                    earliest_dt = datetime.datetime.strptime(db_earliest, "%Y%m%d").date()
                    if target_start < earliest_dt:
                        start_date = target_start
                        end_date = earliest_dt - datetime.timedelta(days=1)
                        logger.info(f"Backfilling history: {start_date} to {end_date} (Requested limit: {sync_range} days).")
                    else:
                        logger.info(f"Database range ({db_earliest} to {db_latest}) already covers requested limit ({sync_range} days).")
                        start_date = end_date + datetime.timedelta(days=1) # Trigger "up to date"
                else:
                    start_date = end_date + datetime.timedelta(days=1)

            if start_date > end_date:
                logger.info("Stock prices are already up to date for the requested range.")
            else:
                logger.info(f"Initiating price sync: {start_date} -> {end_date}")
                try:
                    df = engine.fetch_prices_range(
                        start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d")
                    )
                    if df is not None and not df.empty:
                        engine.ingest_prices(df, session_id)
                        logger.info(f"Successfully finished price sync phase.")
                    else:
                        logger.warning("No price data was returned for the requested period.")
                except Exception as e:
                    logger.error(f"Critical failure in price sync phase: {e}")
                    raise

        if args.sync_market:
            logger.info("--- Phase: Financial Market Sync ---")
            engine.sync_tickers(session_id)
            delay_days = 84
            end_date = datetime.date.today() - datetime.timedelta(days=delay_days)

            # Target Start Date based on limit
            sync_range = args.limit or 180
            target_start = end_date - datetime.timedelta(days=sync_range)

            # Database Coverage
            db_latest = engine.get_latest_fact_date()
            db_earliest = engine.get_earliest_fact_date()

            if not db_latest:
                # Case 1: Empty Database
                start_date = target_start
                logger.info(f"No existing financials. Starting from scratch ({sync_range} days back: {start_date}).")
            else:
                # Case 2: Fill Future
                latest_dt = datetime.datetime.strptime(db_latest, "%Y%m%d").date()
                if latest_dt < end_date:
                    start_date = latest_dt + datetime.timedelta(days=1)
                    logger.info(f"Existing financials found up to {db_latest}. Syncing up to {end_date}.")
                # Case 3: Fill Past
                elif db_earliest:
                    earliest_dt = datetime.datetime.strptime(db_earliest, "%Y%m%d").date()
                    if target_start < earliest_dt:
                        start_date = target_start
                        end_date = earliest_dt - datetime.timedelta(days=1)
                        logger.info(f"Backfilling financial history: {start_date} to {end_date} (Requested limit: {sync_range} days).")
                    else:
                        logger.info(f"Database range ({db_earliest} to {db_latest}) already covers requested financials limit ({sync_range} days).")
                        start_date = end_date + datetime.timedelta(days=1)
                else:
                    start_date = end_date + datetime.timedelta(days=1)

            if start_date > end_date:
                logger.info("Financials are already up to date for the requested range.")
            else:
                logger.info(f"Initiating financial sync: {start_date} -> {end_date}")
                try:
                    df = engine.fetch_fin_range(
                        start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d")
                    )
                    if df is not None and not df.empty:
                        engine.ingest_facts(df, session_id)
                        logger.info(f"Successfully finished financial sync phase.")
                    else:
                        logger.warning("No financial data was returned for the requested period.")
                except Exception as e:
                    logger.error(f"Critical failure in financial sync phase: {e}")
                    raise

        logger.info("J-Quants Provider session completed successfully.")

    except Exception as e:
        logger.critical(f"Fatal error during execution: {e}")
        sys.exit(1)

    # (Indices and Dividends follow similar patterns but restricted on most plans, omitted for brevity but logic stands)


if __name__ == "__main__":
    main()
