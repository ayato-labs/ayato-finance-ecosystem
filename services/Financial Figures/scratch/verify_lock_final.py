import logging
import multiprocessing
import os
import time
from pathlib import Path

import duckdb

from src.api.server import DBManager
from src.core.config import settings

# Setup basic logging
logging.basicConfig(level=logging.INFO, format="%(processName)s: %(message)s")
logger = logging.getLogger(__name__)

TEST_DB = Path("data/test_lock_final.duckdb")


def reader_process():
    """Simulates the refactored API Server."""
    logger.info("Starting API Reader Process (Refactored)...")
    os.environ["DB_READ_ONLY"] = "true"

    # Override settings for test
    settings.DB_PATH_US = TEST_DB

    db = DBManager()

    for i in range(15):
        try:
            with db.get_us_conn() as conn:
                res = conn.execute("SELECT count(*) FROM tickers").fetchone()
                logger.info(f"API Request {i} success: {res}")
            time.sleep(0.5)
        except Exception as e:
            logger.error(f"API Request {i} CRITICAL FAILURE: {e}")


def writer_process():
    """Simulates the Sync Worker."""
    time.sleep(2)
    logger.info("Starting Sync Writer Process...")
    try:
        with duckdb.connect(str(TEST_DB), read_only=False) as conn:
            logger.info("Sync acquired lock. Starting heavy 5s backfill...")
            for i in range(5):
                conn.execute(f"INSERT INTO tickers (ticker, name) VALUES ('F_{i}', 'Full')")
                time.sleep(1)
            logger.info("Sync backfill committed and releasing lock.")
    except Exception as e:
        logger.error(f"Sync failed: {e}")


if __name__ == "__main__":
    if TEST_DB.exists():
        TEST_DB.unlink()

    with duckdb.connect(str(TEST_DB)) as conn:
        conn.execute("CREATE TABLE tickers (ticker VARCHAR, name VARCHAR)")

    p1 = multiprocessing.Process(target=reader_process, name="API-Server")
    p2 = multiprocessing.Process(target=writer_process, name="Sync-Worker")

    p1.start()
    p2.start()

    p1.join()
    p2.join()

    logger.info("Final Verification completed.")
