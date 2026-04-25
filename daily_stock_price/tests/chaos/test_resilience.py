import pytest
import sqlite3
import os
import pandas as pd
from src.engine import MarketDataEngine

def test_chaos_corrupted_parquet(engine, temp_data_dir):
    """Chaos: Handle malformed Parquet files."""
    ticker = "CHAOS_CORRUPT"
    
    # 1. Sync healthy data
    engine.sync_ticker(ticker)
    
    # 2. Get the file path and corrupt it
    paths = engine.catalog.get_paths(ticker)
    corrupt_path = paths[0]
    
    with open(corrupt_path, "wb") as f:
        f.write(b"NOT_A_PARQUET_FILE_JUST_GARBAGE")
    
    # 3. Verify that getting the view doesn't crash but handles the error
    # (DuckDB will throw an error during the query)
    sql = engine.get_synced_view(ticker)
    import duckdb
    db = duckdb.connect()
    
    with pytest.raises(duckdb.Error):
        # We want to ensure that if a file is corrupt, the engine layer 
        # doesn't obfuscate the error but rather allows standard handling
        db.query(sql).to_df()

def test_chaos_catalog_locked(temp_catalog):
    """Chaos: Verify SQLite WAL durability under simulated write locks."""
    # Start a transaction in another connection to hold a lock (Simulated)
    db_path = str(temp_catalog.db_path)
    conn_lock = sqlite3.connect(db_path)
    conn_lock.execute("BEGIN IMMEDIATE TRANSACTION")
    conn_lock.execute("INSERT INTO ticker_index VALUES ('LOCK_TICKER', 'path.pq', 'price')")
    # Do NOT commit yet
    
    # Try to read from the main catalog instance
    # WAL mode allows readers to proceed even if there is a writer
    paths = temp_catalog.get_paths("LOCK_TICKER")
    # Even if LOCK_TICKER is in the journal, it might not be visible 
    # until commit, but the READ itself should not block.
    assert isinstance(paths, list)
    
    conn_lock.close()

def test_chaos_missing_data_dir(engine):
    """Chaos: Handle sudden deletion of data directory."""
    import shutil
    shutil.rmtree(engine.base_dir)
    
    # Verify that sync_ticker recreates the directory instead of crashing
    engine.sync_ticker("RECOVERY_TEST")
    assert os.path.exists(engine.base_dir)
    assert len(engine.catalog.get_paths("RECOVERY_TEST")) == 1
