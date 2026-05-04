import threading
import time

import pytest
from loguru import logger

from src.core.db import db_manager


def simulate_writer(db_path, stop_event):
    """Simulate a continuous background write process."""
    while not stop_event.is_set():
        try:
            with db_manager.connect(db_path, read_only=False) as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO tickers (code, name) VALUES ('9999', 'ChaosTest')"
                )
            time.sleep(0.01)
        except Exception as e:
            # We don't want to crash the thread, but we should log ALL failures.
            # Contention is expected, but should still be traceable at debug level.
            if "lock" in str(e).lower() or "busy" in str(e).lower():
                logger.debug(f"Writer contention (expected): {e}")
            else:
                logger.warning(f"Writer encountered unexpected error: {e}")
            time.sleep(0.1)


def simulate_reader(db_path, stop_event):
    """Simulate a continuous API read process."""
    while not stop_event.is_set():
        try:
            with db_manager.connect(db_path, read_only=True) as conn:
                conn.execute("SELECT * FROM tickers").fetchall()
            time.sleep(0.01)
        except Exception as e:
            # We expect retries, but if we fail outright, the test should record it
            err_msg = str(e).lower()
            if any(kw in err_msg for kw in ["lock", "io error", "busy"]):
                # Expected contention, just log at debug level
                logger.debug(f"Reader contention (expected): {e}")
                time.sleep(0.1)
            else:
                pytest.fail(f"Unexpected reader error: {e}")


def test_chaos_lock_contention(tmp_path):
    """
    Chaos Test: Concurrent Read/Write stress test.
    Ensures that DuckDB lock contention is handled gracefully by our manager.
    """
    db_path = tmp_path / "chaos.duckdb"

    # Setup
    with db_manager.connect(db_path, read_only=False) as conn:
        conn.execute("CREATE TABLE tickers (code VARCHAR PRIMARY KEY, name VARCHAR)")

    stop_event = threading.Event()
    writer = threading.Thread(target=simulate_writer, args=(db_path, stop_event))
    reader = threading.Thread(target=simulate_reader, args=(db_path, stop_event))

    writer.start()
    reader.start()

    time.sleep(2)  # Stress for 2 seconds
    stop_event.set()
    writer.join(timeout=5)
    reader.join(timeout=5)

    assert not writer.is_alive()
    assert not reader.is_alive()
