import datetime
import sys
import time

from loguru import logger

from src.engine import JPEDINETEngine
from src.infra.db import db_manager
from src.infra.logging_config import setup_logging


def setup_progress_table():
    logger.debug("Ensuring ingestion_progress table exists...")
    try:
        with db_manager.connect_master() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_progress (
                    target_date DATE PRIMARY KEY,
                    status VARCHAR, -- 'completed', 'failed'
                    doc_count INTEGER,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
    except Exception as e:
        logger.error(f"Failed to setup progress table: {e}")
        raise


def get_missing_dates(total_days=1825, end_date=None):
    """Finds all dates within the lookback period that are not marked as completed."""
    if end_date is None:
        end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=total_days - 1)

    logger.info(f"Checking missing dates from {start_date} to {end_date}...")
    try:
        with db_manager.connect_master(read_only=True) as conn:
            completed_dates = conn.execute(
                "SELECT target_date FROM ingestion_progress WHERE status = 'completed'"
            ).fetchall()
            completed_set = {
                row[0].date() if isinstance(row[0], datetime.datetime) else row[0]
                for row in completed_dates
            }
            logger.debug(f"Found {len(completed_set)} completed dates in registry.")
    except Exception as e:
        logger.warning(f"Could not fetch progress metadata: {e}. Starting fresh.")
        completed_set = set()

    missing = []
    curr = start_date
    while curr <= end_date:
        if curr not in completed_set:
            missing.append(curr)
        curr += datetime.timedelta(days=1)

    return missing


def main():
    print("DEBUG: Entered main")
    setup_logging()
    logger.info("Starting Resilient Historical Fetch Service...")

    try:
        engine = JPEDINETEngine()
        setup_progress_table()

        # Configuration
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--days", type=int, default=1825)
        parser.add_argument("--end-date", type=str, default=None)
        args = parser.parse_args()

        LOOKBACK_DAYS = args.days
        end_date = datetime.date.fromisoformat(args.end_date) if args.end_date else datetime.date.today()
        
        missing_dates = get_missing_dates(LOOKBACK_DAYS, end_date)

        if not missing_dates:
            logger.info("No dates to process.")
            return

        logger.info(f"Identified {len(missing_dates)} dates requiring ingestion.")

        # Process from newest to oldest
        processed_in_session = 0
        for target_date in reversed(missing_dates):
            logger.info(f"--- Processing Date: {target_date} ---")

            session_id = f"hist-{target_date.isoformat()}"
            try:
                # Sync exactly this day, skip vacuum to avoid lock contention in loop
                engine.sync_market(
                    days=1, end_date=target_date, session_id=session_id, run_vacuum=False
                )

                # Record success
                with db_manager.connect_master() as conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO ingestion_progress (target_date, status, updated_at)
                        VALUES (?, 'completed', CURRENT_TIMESTAMP)
                        """,
                        [target_date],
                    )

                logger.info(f"✅ Successfully completed ingestion for {target_date}")
                processed_in_session += 1

                # Every 50 days, run a vacuum to reclaim space without being too aggressive
                if processed_in_session % 50 == 0:
                    logger.info("Periodic maintenance: running VACUUM...")
                    engine._vacuum_db()

            except Exception as e:
                logger.error(f"❌ Failed to process {target_date}: {e}", exc_info=True)
                try:
                    with db_manager.connect_master() as conn:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO ingestion_progress
                            (target_date, status, updated_at)
                            VALUES (?, 'failed', CURRENT_TIMESTAMP)
                            """,
                            [target_date],
                        )
                except Exception as db_err:
                    logger.critical(f"Could not even record failure to DB: {db_err}")

                # Wait longer on error to let API rate limits reset
                time.sleep(10)

        logger.info("Historical ingestion pipeline finished execution.")

    except KeyboardInterrupt:
        logger.warning("Service interrupted by user.")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Historical loader crashed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
