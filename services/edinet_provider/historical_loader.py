import datetime
import time
from loguru import logger
from src.engine import JPEDINETEngine
from src.core.db import db_manager

def setup_progress_table():
    with db_manager.connect_master() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ingestion_progress (
                target_date DATE PRIMARY KEY,
                status VARCHAR, -- 'completed', 'failed'
                doc_count INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

def get_missing_dates(total_days=1825):
    """Finds all dates within the lookback period that are not marked as completed."""
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=total_days - 1)
    
    with db_manager.connect_master(read_only=True) as conn:
        completed_dates = conn.execute("SELECT target_date FROM ingestion_progress WHERE status = 'completed'").fetchall()
        completed_set = {row[0].date() if isinstance(row[0], datetime.datetime) else row[0] for row in completed_dates}

    missing = []
    curr = start_date
    while curr <= end_date:
        if curr not in completed_set:
            missing.append(curr)
        curr += datetime.timedelta(days=1)
    
    return missing

def main():
    engine = JPEDINETEngine()
    setup_progress_table()
    
    # Configuration
    LOOKBACK_DAYS = 1825  # 5 years
    
    missing_dates = get_missing_dates(LOOKBACK_DAYS)
    
    if not missing_dates:
        logger.info("All dates within the lookback period are already completed. Nothing to do.")
        return

    logger.info(f"Found {len(missing_dates)} missing dates to process.")
    
    # Process from newest to oldest for better relevance
    for target_date in reversed(missing_dates):
        logger.info(f"--- Processing Date: {target_date} ---")
        
        session_id = f"delta-{target_date.isoformat()}"
        try:
            # Sync exactly this day
            engine.sync_market(days=1, end_date=target_date, session_id=session_id)
            
            # Record success
            with db_manager.connect_master() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO ingestion_progress (target_date, status, updated_at)
                    VALUES (?, 'completed', CURRENT_TIMESTAMP)
                """, [target_date])
            
            logger.info(f"✅ Successfully completed {target_date}")
            
        except Exception as e:
            logger.error(f"❌ Failed to process {target_date}: {e}")
            with db_manager.connect_master() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO ingestion_progress (target_date, status, updated_at)
                    VALUES (?, 'failed', CURRENT_TIMESTAMP)
                """, [target_date])
            # Brief wait on failure
            time.sleep(5)

    logger.info("Historical / Delta sync process finished.")

if __name__ == "__main__":
    main()
