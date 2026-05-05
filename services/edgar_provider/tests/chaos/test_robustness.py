import pytest
import threading
import time
import duckdb
from src.core.db import db_manager
from src.core.config import settings
from src.engine import USEngine

def test_chaos_db_locking():
    """Chaos Test: Multiple threads competing for the same database."""
    db_path = settings.FACTS_DB_PATH
    engine = USEngine() # Triggers migration
    
    errors = []
    
    def heavy_writer():
        try:
            with db_manager.connect(db_path, timeout_seconds=5) as conn:
                for i in range(100):
                    conn.execute("INSERT INTO metrics (run_id, step_name, status) VALUES (?, ?, ?)", 
                                 [f"chaos-{i}", "chaos_step", "success"])
                    time.sleep(0.01) # Hold lock briefly
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=heavy_writer) for _ in range(5)]
    for t in threads: threads.start()
    for t in threads: t.join()
    
    # We expect our DuckDBManager to handle retries and succeed
    assert len(errors) == 0, f"Encountered {len(errors)} locking errors: {errors}"

def test_chaos_malformed_json_bulk():
    """Chaos Test: Ingesting malformed JSON strings in bulk process."""
    from src.engine import parse_company_facts_json, _init_worker
    
    _init_worker({"123": "FAKE"}, "chaos-session")
    
    # Should not crash, should return empty list (per our robust try-except)
    records = parse_company_facts_json("corrupt.json", "{ 'invalid': json ...")
    assert records == []

def test_chaos_null_primary_keys():
    """Chaos Test: Attempting to save records with NULL in Primary Key columns."""
    engine = USEngine()
    
    # These records have NULLs in Primary Key fields (ticker, accession, label)
    bad_records = [
        (None, "cik", "accn", "form", "2024-01-01", 2023, "FY", "Label", 1.0, "USD", True, "tag", "sid"),
        ("AAPL", "cik", None, "form", "2024-01-01", 2023, "FY", "Label", 1.0, "USD", True, "tag", "sid"),
        ("AAPL", "cik", "accn", "form", "2024-01-01", 2023, "FY", None, 1.0, "USD", True, "tag", "sid")
    ]
    
    # Act & Assert: Should filter them out defensively in _save_raw_facts
    # and NOT raise a duckdb.ConstraintException
    try:
        engine._save_raw_facts(bad_records)
    except duckdb.ConstraintException:
        pytest.fail("USEngine._save_raw_facts did not filter NULL primary keys!")
    
    with db_manager.connect(engine.facts_db) as conn:
        count = conn.execute("SELECT count(*) FROM company_facts").fetchone()[0]
        assert count == 0
