import sys
import os
import datetime
import time
from pathlib import Path

# Add project root to sys.path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from loguru import logger
from src.core.logging import setup_logging
from src.providers.jquants.engine import JPEngine
from src.core.audit_manager import audit_manager

def main():
    setup_logging()
    logger.info("Starting J-Quants Standalone Sync...")
    try:
        engine = JPEngine()
        session_id = audit_manager.start_session("JP")
        
        logger.info(f"Session ID: {session_id}")
        
        # Sync tickers first
        engine.sync_tickers(session_id)
        
        # J-Quants Free Plan: 12-week (84 days) delay
        delay_days = 84
        sync_range = 30 # Just sync last 30 days for standalone script
        base_date = datetime.date.today() - datetime.timedelta(days=delay_days)
        
        count = 0
        for i in range(sync_range):
            d = base_date - datetime.timedelta(days=i)
            if d.weekday() < 5:
                try:
                    df = engine.cli.get_fin_summary(date_yyyymmdd=d.strftime("%Y%m%d"))
                    if df is not None and not df.empty:
                        logger.info(f"Ingesting JP summary for {d.strftime('%Y-%m-%d')} ({len(df)} records)")
                        # Directly ingest in this standalone script
                        code_col = "LocalCode" if "LocalCode" in df.columns else "Code"
                        for code in df[code_col].unique():
                            engine.ingest_facts(str(code), df[df[code_col] == code], session_id)
                        count += 1
                except Exception as e:
                    logger.error(f"Error fetching JP summary for {d}: {e}")
                
                time.sleep(1.2) # Rate limit respect

        audit_manager.end_session(session_id, "SUCCESS", count, 0)
        logger.info(f"J-Quants Sync Completed. Processed {count} days of data.")
    except Exception as e:
        logger.error(f"J-Quants Sync Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
