import pytest
import tempfile
import sqlite3 # Just for comparison if needed, but we use DuckDB
from pathlib import Path
from src.core.migrations import MigrationManager
from src.core.db import db_manager
from src.core.schema import TABLE_SCHEMAS

@pytest.fixture
def migration_env(mocker):
    tmpdir = tempfile.TemporaryDirectory()
    base_path = Path(tmpdir.name)
    mocker.patch("src.core.config.settings.DATA_DIR", base_path)
    mocker.patch("src.core.config.settings.MASTER_DB_PATH", str(base_path / "master.duckdb"))
    mocker.patch("src.core.config.settings.JP_MASTER_DB_PATH", str(base_path / "jquants_master.duckdb"))
    mocker.patch("src.core.config.settings.JP_PRICES_DB_PATH", str(base_path / "jquants_prices.duckdb"))
    mocker.patch("src.core.config.settings.JP_FACTS_DB_PATH", str(base_path / "jquants_financials.duckdb"))
    
    yield base_path
    tmpdir.cleanup()

def test_migration_version_tracking(migration_env):
    """Verify that migration history is correctly tracked."""
    # 1. First run: apply everything
    MigrationManager.apply_migrations()
    
    # 2. Check history table in master
    with db_manager.connect(migration_env / "master.duckdb") as conn:
        res = conn.execute("SELECT version FROM __migrations_history WHERE table_name = 'tickers'").fetchone()
        assert res is not None
        assert res[0] == TABLE_SCHEMAS["tickers"]["version"]

def test_migration_idempotency(migration_env):
    """Verify that running migration twice doesn't cause errors."""
    MigrationManager.apply_migrations()
    # Second run should be silent and successful
    MigrationManager.apply_migrations()
