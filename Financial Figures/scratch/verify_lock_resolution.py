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

TEST_DB = Path("data/test_lock.duckdb")


def reader_process():
    """Simulates the API Server."""
    logger.info("Starting Reader Process (emulating API)...")
    os.environ["DB_READ_ONLY"] = "true"

    # We must ensure the DB exists first, as a reader cannot create it
    # (In real life, the sync or a previous run would have created it)

    try:
        # Use USEngine which now respects DB_READ_ONLY
        engine = USEngine()
        # Explicitly set the path for test
        engine.db_path = TEST_DB

        logger.info(f"Reader attempting connection to {TEST_DB}...")
        # Note: _init_db should be skipped in read_only mode
        engine._init_db()

        with duckdb.connect(str(TEST_DB), read_only=True) as conn:
            logger.info("Reader connected successfully. Holding connection for 5 seconds...")
            time.sleep(5)
            res = conn.execute("SELECT count(*) FROM tickers").fetchone()
            logger.info(f"Reader read result: {res}")

    except Exception as e:
        logger.error(f"Reader failed: {e}", exc_info=True)


def writer_process():
    """Simulates the Sync Worker."""
    time.sleep(2)  # Give reader time to start
    logger.info("Starting Writer Process (emulating Sync)...")
    os.environ["DB_READ_ONLY"] = "false"

    try:
        engine = USEngine()
        engine.db_path = TEST_DB

        logger.info(f"Writer attempting connection to {TEST_DB}...")
        # Writer should be able to init and write even if reader is active
        engine._init_db()

        with duckdb.connect(str(TEST_DB), read_only=False) as conn:
            logger.info("Writer connected successfully. Performing write...")
            conn.execute(
                "INSERT INTO tickers (ticker, cik, name) VALUES ('TEST', '000', 'Test Corp')"
            )
            logger.info("Writer committed successfully.")

    except Exception as e:
        logger.error(f"Writer failed: {e}", exc_info=True)


if __name__ == "__main__":
    # 1. Clean up old test DB
    if TEST_DB.exists():
        TEST_DB.unlink()

    # 2. Create the DB first (since reader can't create it)
    logger.info("Initializing test database...")
    with duckdb.connect(str(TEST_DB)) as conn:
        conn.execute("CREATE TABLE tickers (ticker VARCHAR, cik VARCHAR, name VARCHAR)")

    # 3. Start parallel processes
    p1 = multiprocessing.Process(target=reader_process, name="API-Reader")
    p2 = multiprocessing.Process(target=writer_process, name="Sync-Writer")

    p1.start()
    p2.start()

    p1.join()
    p2.join()

    logger.info("Verification completed.")
