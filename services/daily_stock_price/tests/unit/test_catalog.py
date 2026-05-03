import sqlite3

from src.catalog import CatalogManager

# Constants for testing
BUSY_TIMEOUT_MS = 5000
EXPECTED_PATH_COUNT = 2

def test_catalog_initialization(temp_data_dir):
    """Verify that catalog initializes with correct schema and WAL mode."""
    db_path = temp_data_dir / "catalog_test.sqlite"
    CatalogManager(db_path=db_path)
    with sqlite3.connect(str(db_path)) as conn:
        # Check WAL mode
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"

        # Check Busy Timeout
        timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        assert timeout == BUSY_TIMEOUT_MS

        # Check schema
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        assert ("ticker_index",) in tables

def test_catalog_register_and_get(temp_catalog):
    """Verify registration and retrieval logic."""
    temp_catalog.register_many([
        ("AAPL", "path/1.parquet", "price"), ("AAPL", "path/2.parquet", "price")
    ])

    paths = temp_catalog.get_paths("AAPL")
    assert len(paths) == EXPECTED_PATH_COUNT
    assert "path/1.parquet" in paths
    assert "path/2.parquet" in paths

    # Check non-existent
    assert temp_catalog.get_paths("UNKNOWN") == []

def test_catalog_clear(temp_catalog):
    """Verify that clear() empties the index."""
    temp_catalog.register_many([("MSFT", "p.parquet", "price")])
    assert len(temp_catalog.get_paths("MSFT")) == 1

    temp_catalog.clear()
    assert len(temp_catalog.get_paths("MSFT")) == 0
