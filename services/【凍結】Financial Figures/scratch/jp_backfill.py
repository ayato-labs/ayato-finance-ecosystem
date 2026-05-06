import datetime
import time
import pandas as pd
from loguru import logger
from src.engines.jp_engine import JPEngine
from src.core.db import db_manager
from src.core.audit_manager import audit_manager

def jp_full_backfill():
    engine = JPEngine()
    session_id = audit_manager.start_session("JP_BACKFILL_FINAL_STABLE")
    
    # J-Quants Free Plan window: ~2 years ending 12 weeks ago
    sub_end = datetime.date(2026, 2, 9)
    sub_start = datetime.date(2024, 2, 9)
    
    logger.info(f"Starting STABLE JP Backfill: {sub_start} to {sub_end}")
    
    current_date = sub_end
    records_ingested = 0
    consecutive_errors = 0
    
    try:
        while current_date >= sub_start:
            date_str = current_date.strftime("%Y%m%d")
            
            if current_date.weekday() >= 5:
                current_date -= datetime.timedelta(days=1)
                continue
                
            try:
                with db_manager.connect(engine.db_path, read_only=True) as conn:
                    exists = conn.execute(
                        "SELECT 1 FROM company_facts WHERE DisclosedDate = ? LIMIT 1",
                        [current_date.strftime("%Y-%m-%d")]
                    ).fetchone()
            except Exception as e:
                logger.error(f"DB check failed: {e}")
                exists = False
            
            if exists:
                current_date -= datetime.timedelta(days=1)
                continue
                
            logger.info(f"Fetching JP summary for {date_str} (Total: {records_ingested})...")
            success = False
            
            for attempt in range(3):
                try:
                    df = engine.cli.get_fin_summary(date_yyyymmdd=date_str)
                    if df is not None and not df.empty:
                        engine.ingest_facts("bulk", df, session_id)
                        records_ingested += len(df)
                        logger.info(f"Ingested {len(df)} records for {current_date}")
                    
                    success = True
                    consecutive_errors = 0
                    break
                    
                except Exception as e:
                    err_msg = str(e)
                    if "429" in err_msg:
                        # 429 on 13s delay means we are probably flagged. Sleep longer.
                        wait_time = 300 # 5 minutes block
                        logger.warning(f"Rate limited (429). Server block? Sleeping for 5 mins...")
                        time.sleep(wait_time)
                    elif "400" in err_msg and "subscription" in err_msg.lower():
                        logger.warning(f"Subscription error at {current_date}: {err_msg}")
                        success = True # Treat as "no data/out of window" and skip
                        break
                    else:
                        wait_time = 30 * (attempt + 1)
                        logger.warning(f"Attempt {attempt+1} failed for {current_date}: {err_msg}. Sleeping {wait_time}s")
                        time.sleep(wait_time)
            
            if not success:
                consecutive_errors += 1
                if consecutive_errors > 10:
                    logger.error("Too many consecutive errors. Aborting.")
                    break
            
            current_date -= datetime.timedelta(days=1)
            
            # 13.0 seconds delay to stay under 5 req/min (60s / 5 = 12s)
            time.sleep(13.0)
            
        audit_manager.end_session(session_id, "SUCCESS", records_ingested, 0)
        logger.info(f"Backfill finished. Total ingested: {records_ingested}")
        
    except Exception as e:
        logger.error(f"Critical backfill error: {e}")
        audit_manager.end_session(session_id, "FAILED", records_ingested, 1, str(e))

if __name__ == "__main__":
    jp_full_backfill()
