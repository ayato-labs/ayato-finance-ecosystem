import datetime
import pandas as pd
from src.services.market_sync import BatchSyncService
from loguru import logger
import time

def verify_sync():
    service = BatchSyncService(start_workers=True)
    session_id = "verify-sync-v2"
    # Use a date in the allowed window
    test_date = datetime.date(2026, 2, 5)
    date_str = test_date.strftime("%Y%m%d")
    
    logger.info(f"Triggering verification sync for {date_str}...")
    try:
        df = service.jp_engine.cli.get_fin_summary(date_yyyymmdd=date_str)
        if df is not None and not df.empty:
            logger.info(f"Fetched {len(df)} records. Queuing for ingestion...")
            service.jp_db_queue.put(("JP_BULK", date_str, df, session_id))
            
            # Wait for workers to process
            logger.info("Waiting for JP_Writer to finish...")
            service.jp_db_queue.join()
            service.audit_db_queue.join()
            logger.info("Sync verified.")
        else:
            logger.warning("No records found for test date.")
    except Exception as e:
        logger.error(f"Verification sync failed: {e}")
    finally:
        service.stop()

if __name__ == "__main__":
    verify_sync()
