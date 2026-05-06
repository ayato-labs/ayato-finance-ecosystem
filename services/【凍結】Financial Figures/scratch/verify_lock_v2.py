import logging
import multiprocessing
import os
import time
from pathlib import Path

import duckdb

from src.engines.us_engine import USEngine

# Setup basic logging
logging.basicConfig(level=logging.INFO, format="%(processName)s: %(message)s")
logger = logging.getLogger(__name__)

TEST_DB = Path("data/test_lock_v2.duckdb")


def writer_process():
    """Simulates the Sync Worker."""
    logger.info("Starting Writer Process (emulating Sync)...")
    os.environ["DB_READ_ONLY"] = "false"

    try:
        engine = USEngine()
        engine.db_path = TEST_DB

        logger.info(f"Writer attempting connection to {TEST_DB}...")
        engine._init_db()

        # Keep connection open
        with duckdb.connect(str(TEST_DB), read_only=False) as conn:
            logger.info("Writer connected successfully. Holding connection for 10 seconds...")
            conn.execute(
                "INSERT INTO tickers (ticker, cik, name) VALUES ('WRITER_FIRST', '111', 'Writer Corp')"
            )
            time.sleep(10)
            logger.info("Writer closing.")

    except Exception as e:
        logger.error(f"Writer failed: {e}", exc_info=True)


def reader_process():
    """Simulates the API Server."""
    time.sleep(3)  # Ensure writer is already holding the lock
    logger.info("Starting Reader Process (emulating API)...")
    os.environ["DB_READ_ONLY"] = "true"

    try:
        engine = USEngine()
        engine.db_path = TEST_DB

        logger.info(f"Reader attempting connection to {TEST_DB} in READ_ONLY mode...")
        # Note: _init_db should be skipped in read_only mode due to my fix
        engine._init_db()

        with duckdb.connect(str(TEST_DB), read_only=True) as conn:
            logger.info("Reader connected successfully while writer was active!")
            res = conn.execute("SELECT count(*) FROM tickers").fetchone()
            logger.info(f"Reader read result: {res}")

    except Exception as e:
        logger.error(f"Reader failed: {e}", exc_info=True)


if __name__ == "__main__":
    # 1. Clean up old test DB
    if TEST_DB.exists():
        TEST_DB.unlink()

    # 2. Start parallel processes
    p_writer = multiprocessing.Process(target=writer_process, name="Sync-Writer")
    p_reader = multiprocessing.Process(target=reader_process, name="API-Reader")

    p_writer.start()
    p_reader.start()

    p_writer.join()
    p_reader.join()

    logger.info("Verification v2 completed.")
