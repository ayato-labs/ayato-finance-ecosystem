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
                status VARCHAR, -- 'pending', 'completed', 'failed'
                doc_count INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

def get_next_pending_month(start_date, end_date):
    """Returns the start and end of the next 30-day window to process."""
    with db_manager.connect_master(read_only=True) as conn:
        # Simple logic: find the latest completed date and go back 30 days
        # For simplicity in this loader, we will just iterate back from today
        pass

def main():
    engine = JPEDINETEngine()
    setup_progress_table()
    
    total_days = 1825
    step_days = 30
    end_date = datetime.date.today()
    
    logger.info(f"Starting historical load for {total_days} days in {step_days}-day increments.")
    
    for start_offset in range(0, total_days, step_days):
        batch_end = end_date - datetime.timedelta(days=start_offset)
        batch_start = batch_end - datetime.timedelta(days=step_days - 1)
        
        # Adjust batch_start to not exceed the total_days limit
        if (end_date - batch_start).days >= total_days:
            batch_start = end_date - datetime.timedelta(days=total_days - 1)

        # Check if already completed
        with db_manager.connect_master(read_only=True) as conn:
            res = conn.execute("SELECT status FROM ingestion_progress WHERE target_date = ?", [batch_start]).fetchone()
            if res and res[0] == 'completed':
                logger.info(f"Skipping period {batch_start} to {batch_end} (Already completed)")
                continue

        logger.info(f"--- Processing Period: {batch_start} to {batch_end} ---")
        
        session_id = f"hist-{batch_start.isoformat()}"
        try:
            # Sync this month
            # We use a custom loop here instead of engine.sync_market to have direct control over the dates
            engine.sync_market(days=(batch_end - batch_start).days + 1, end_date=batch_end, session_id=session_id)
            
            # Record success
            with db_manager.connect_master() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO ingestion_progress (target_date, status, updated_at)
                    VALUES (?, 'completed', CURRENT_TIMESTAMP)
                """, [batch_start])
            
            logger.info(f"Successfully completed period up to {batch_start}")
            
            # Cool down between months to respect API limits
            logger.info("Cooling down for 5 seconds...")
            time.sleep(5)
            
        except Exception as e:
            logger.error(f"Failed to process period {batch_start}: {e}")
            with db_manager.connect_master() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO ingestion_progress (target_date, status, updated_at)
                    VALUES (?, 'failed', CURRENT_TIMESTAMP)
                """, [batch_start])
            logger.info("Waiting 30 seconds before retrying next batch...")
            time.sleep(30)

    logger.info("Historical load process finished.")

if __name__ == "__main__":
    main()
