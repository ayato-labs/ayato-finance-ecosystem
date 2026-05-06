import pytest
import duckdb
from src.core.db import db_manager

def test_db_manager_memory_connection():
    """
    Unit Test: Verify DuckDBManager handles in-memory connections correctly.
    """
    with db_manager.connect_master() as conn:
        assert conn is not None
        # Check if master tables exist
        res = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_name = 'schema_version'").fetchone()
        assert res is not None

def test_db_manager_thread_safety():
    """
    Unit Test: Simple check on lock behavior (implicit).
    """
    import threading
    
    def connect_work():
        with db_manager.connect_master() as conn:
            conn.execute("SELECT 1")
    
    threads = [threading.Thread(target=connect_work) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    # If no exception, lock coordination works within same process
