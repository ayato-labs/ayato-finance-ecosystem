from pathlib import Path

import pytest
from edgar_core.config import settings
from edgar_core.db import db_manager


def test_db_manager_lifecycle(tmp_path):
    """
    Unit Test: Verify DuckDB connection lifecycle and PRAGMA settings.
    No mocks allowed.
    """
    test_db = tmp_path / "lifecycle.duckdb"
    
    # 1. Connect and Create
    with db_manager.connect(test_db, read_only=False) as conn:
        conn.execute("CREATE TABLE unit_test (id INTEGER)")
        conn.execute("INSERT INTO unit_test VALUES (1)")
        res = conn.execute("SELECT * FROM unit_test").fetchone()
        assert res[0] == 1
    
    # 2. Reconnect Read-Only
    with db_manager.connect(test_db, read_only=True) as conn:
        res = conn.execute("SELECT count(*) FROM unit_test").fetchone()
        assert res[0] == 1
        
        # Verify write protection
        with pytest.raises(Exception) as excinfo:
            conn.execute("INSERT INTO unit_test VALUES (2)")
        assert "read-only" in str(excinfo.value).lower()

def test_db_manager_lock_retry(tmp_path):
    """
    Unit Test: Verify lock acquisition retry logic using a thread.
    No mocks.
    """
    import threading
    import time
    
    db_path = tmp_path / "lock.duckdb"
    # Ensure file exists
    import duckdb
    duckdb.connect(str(db_path)).close()
    
    lock_event = threading.Event()
    release_event = threading.Event()
    
    def hold_lock():
        with duckdb.connect(str(db_path), read_only=False) as conn:
            lock_event.set()
            # Hold lock for 2 seconds
            time.sleep(2)
            release_event.set()

    t = threading.Thread(target=hold_lock)
    t.start()
    
    lock_event.wait()
    # Now try to connect via manager, which should retry
    start = time.time()
    with db_manager.connect(db_path, timeout_seconds=5) as conn:
        elapsed = time.time() - start
        assert elapsed >= 1.0 # Should have waited at least one retry interval
        conn.execute("SELECT 1")
    
    t.join()
