import argparse
import datetime
import sys
import time

from loguru import logger

from src.datalake.engine import JPEDINETEngine
from src.datalake.shared.infra.db import db_manager
from src.datalake.shared.infra.logging_config import setup_logging


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
    setup_logging()
    logger.info("Starting Resilient Historical Fetch Service...")

    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--days", type=int, default=1825)
        parser.add_argument("--end-date", type=str, default=None)
        args = parser.parse_args()

        engine = JPEDINETEngine()
        setup_progress_table()

        lookback = args.days
        end_dt = (
            datetime.date.fromisoformat(args.end_date)
            if args.end_date
            else datetime.date.today()
        )

        missing_dates = get_missing_dates(lookback, end_dt)

        if not missing_dates:
            logger.info("No dates to process.")
            return

        logger.info(f"Identified {len(missing_dates)} dates requiring ingestion.")

        # Process from newest to oldest in chunks to reduce startup/shutdown overhead
        CHUNK_SIZE = 7
        missing_dates = sorted(missing_dates, reverse=True)
        processed_in_session = 0

        for i in range(0, len(missing_dates), CHUNK_SIZE):
            chunk = missing_dates[i : i + CHUNK_SIZE]
            start_chunk_dt = chunk[-1]
            end_chunk_dt = chunk[0]
            logger.info(f"--- Processing Chunk: {end_chunk_dt} back to {start_chunk_dt} ({len(chunk)} days) ---")

            try:
                # Sync the whole chunk at once
                # Note: sync_market handles the range internally
                days_in_range = (end_chunk_dt - start_chunk_dt).days + 1
                session_id = f"hist-chunk-{end_chunk_dt.isoformat()}"
                
                engine.sync_market(
                    days=days_in_range, 
                    end_date=end_chunk_dt, 
                    session_id=session_id, 
                    run_vacuum=False
                )

                # Record success for each day in the chunk that was actually processed
                with db_manager.connect_master() as conn:
                    for target_date in chunk:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO ingestion_progress (target_date, status, updated_at)
                            VALUES (?, 'completed', CURRENT_TIMESTAMP)
                            """,
                            [target_date],
                        )
                
                logger.info(f"✅ Successfully completed chunk ending at {end_chunk_dt}")
                processed_in_session += len(chunk)

                if processed_in_session % 50 <= CHUNK_SIZE and processed_in_session >= 50:
                    logger.info("Periodic maintenance: running VACUUM...")
                    engine._vacuum_db()

            except Exception as e:
                logger.error(f"❌ Failed to process chunk ending at {end_chunk_dt}: {e}", exc_info=True)
                # On failure, we don't mark individual dates as failed here to allow retry on next run
                # But we wait to avoid spamming the API
                time.sleep(20)

        logger.info("Historical ingestion pipeline finished execution.")

    except KeyboardInterrupt:
        logger.warning("Service interrupted by user.")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Historical loader crashed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
