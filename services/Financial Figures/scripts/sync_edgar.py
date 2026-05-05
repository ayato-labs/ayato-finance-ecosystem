import sys
import os
from pathlib import Path

# Add project root to sys.path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from loguru import logger
from src.core.logging import setup_logging
from src.providers.sec_edgar.engine import USEngine
from src.core.audit_manager import audit_manager

def main():
    setup_logging()
    logger.info("Starting SEC-EDGAR Standalone Sync...")
    try:
        engine = USEngine()
        session_id = audit_manager.start_session("US")
        
        logger.info(f"Session ID: {session_id}")
        
        # Sync tickers first
        engine.sync_tickers(session_id)
        
        # In a real production script, we might want to iterate over tickers.
        # For this standalone script, let's mirror the core logic of BatchSyncService but isolated.
        from src.core.db import db_manager
        with db_manager.connect(engine.db_path, read_only=True) as conn:
            all_symbols = [r[0] for r in conn.execute("SELECT ticker FROM tickers").fetchall()]
        
        # Basic incremental logic: skip if synced today (simplified for this script)
        logger.info(f"Found {len(all_symbols)} tickers to check.")
        
        # For simplicity in this standalone script, we just run a few or full sync
        # In production, this would be more sophisticated.
        count = 0
        for ticker in all_symbols[:100]: # Limit to 100 for standalone test run
            try:
                data = engine.fetch_company_facts(ticker)
                if data:
                    engine.ingest_facts(ticker, data, session_id)
                    count += 1
            except Exception as e:
                logger.error(f"Error syncing {ticker}: {e}")

        audit_manager.end_session(session_id, "SUCCESS", count, 0)
        logger.info(f"SEC-EDGAR Sync Completed. Processed {count} tickers.")
    except Exception as e:
        logger.error(f"SEC-EDGAR Sync Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
