import threading
import time

import duckdb
import pytest

from src.infra.db import db_manager


def test_heavy_contention_resilience(tmp_path, monkeypatch):
    """
    Hardening: Force multiple threads to fight for a physical DB lock.
    Tests if the retry logic in connect_master actually works.
    """
    db_file = tmp_path / "contention.db"
    monkeypatch.setenv("MASTER_DB_PATH", str(db_file))
    monkeypatch.setenv("REGISTRY_DB_PATH", str(tmp_path / "reg.db"))
    monkeypatch.setenv("FACTS_DB_PATH", str(tmp_path / "facts.db"))
    monkeypatch.setenv("NARRATIVE_DB_PATH", str(tmp_path / "narr.db"))
    
    # Initialize DB
    with db_manager.connect_master() as conn:
        conn.execute("CREATE TABLE counter (v INTEGER)")
        conn.execute("INSERT INTO counter VALUES (0)")

    def slow_write():
        # Hold a connection for a long time to block others
        try:
            with db_manager.connect_master() as conn:
                time.sleep(2) # Hold the lock
                conn.execute("UPDATE counter SET v = v + 1")
        except Exception as e:
            pytest.fail(f"Slow write failed: {e}")

    def fast_retry_write():
        # Try to write while slow_write holds the lock
        time.sleep(0.5) # Wait for slow_write to start
        try:
            with db_manager.connect_master(timeout_seconds=10) as conn:
                conn.execute("UPDATE counter SET v = v + 1")
        except Exception as e:
            pytest.fail(f"Retry write failed: {e}")

    t1 = threading.Thread(target=slow_write)
    t2 = threading.Thread(target=fast_retry_write)
    
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()
    
    with db_manager.connect_master(read_only=True) as conn:
        val = conn.execute("SELECT v FROM counter").fetchone()[0]
        assert val == 2 # Both should have succeeded eventually

def test_invalid_sql_not_suppressed():
    """
    Hardening: Ensure that errors are NOT suppressed (no silent 'pass').
    """
    with db_manager.connect_master() as conn:
        with pytest.raises(duckdb.ParserException):
            conn.execute("INVALID SQL STATEMENT")
