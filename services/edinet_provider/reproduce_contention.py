import threading
import time
import os
import duckdb
from pathlib import Path
from src.core.db import db_manager
from src.core.config import settings
from loguru import logger

def long_writer(db_path, duration=5):
    logger.info("Long writer starting...")
    with db_manager.connect_master() as conn:
        logger.info("Long writer acquired lock.")
        conn.execute("CREATE TABLE IF NOT EXISTS registry_db.sync_lock (id INTEGER)")
        time.sleep(duration)
        logger.info("Long writer releasing lock.")

def quick_reader():
    logger.info("Quick reader starting...")
    start = time.time()
    try:
        with db_manager.connect_master(read_only=True, timeout_seconds=10) as conn:
            logger.info(f"Quick reader acquired lock after {time.time() - start:.2f}s.")
            res = conn.execute("SELECT count(*) FROM registry_db.filings").fetchone()
            logger.info(f"Quick reader result: {res}")
    except Exception as e:
        logger.error(f"Quick reader failed: {e}")

if __name__ == "__main__":
    # Ensure physical files
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Run a writer in a thread (to simulate another process/thread)
    t1 = threading.Thread(target=long_writer, args=(settings.MASTER_DB_PATH, 3))
    t1.start()
    
    time.sleep(0.5) # Give it time to grab the lock
    
    # Run a reader
    quick_reader()
    
    t1.join()
    logger.info("Test complete.")
