import logging
import multiprocessing
import time
from pathlib import Path

import duckdb

# Setup basic logging
logging.basicConfig(level=logging.INFO, format="%(processName)s: %(message)s")
logger = logging.getLogger(__name__)

TEST_DB = Path("data/test_lock_v3.duckdb")


def reader_process():
    """Simulates the API Server using short-lived connections."""
    logger.info("Starting Reader Process (Short-lived)...")
    for i in range(10):
        try:
            with duckdb.connect(str(TEST_DB), read_only=True) as conn:
                res = conn.execute("SELECT count(*) FROM tickers").fetchone()
                logger.info(f"Reader read {i}: {res}")
            time.sleep(1)  # Gap for writer to enter
        except Exception as e:
            logger.warning(f"Reader attempt {i} failed (likely locked): {e}")
            time.sleep(0.5)


def writer_process():
    """Simulates the Sync Worker."""
    time.sleep(2)
    logger.info("Starting Writer Process...")
    try:
        # Long-ish write operation
        with duckdb.connect(str(TEST_DB), read_only=False) as conn:
            logger.info("Writer acquired lock. Performing 5s write...")
            for i in range(5):
                conn.execute(f"INSERT INTO tickers (ticker, cik, name) VALUES ('W_{i}', '0', 'W')")
                time.sleep(1)
            logger.info("Writer committed and releasing lock.")
    except Exception as e:
        logger.error(f"Writer failed: {e}")


if __name__ == "__main__":
    if TEST_DB.exists():
        TEST_DB.unlink()

    with duckdb.connect(str(TEST_DB)) as conn:
        conn.execute("CREATE TABLE tickers (ticker VARCHAR, cik VARCHAR, name VARCHAR)")

    p1 = multiprocessing.Process(target=reader_process, name="API-Reader")
    p2 = multiprocessing.Process(target=writer_process, name="Sync-Writer")

    p1.start()
    p2.start()

    p1.join()
    p2.join()

    logger.info("Verification v3 completed.")
