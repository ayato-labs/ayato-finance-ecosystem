import pytest
import pandas as pd
import tempfile
from pathlib import Path
from src.engine import JPEngine
from src.core.db import db_manager

@pytest.fixture
def sharded_env(mocker):
    tmpdir = tempfile.TemporaryDirectory()
    base_path = Path(tmpdir.name)
    mocker.patch("src.core.config.settings.DATA_DIR", base_path)
    mocker.patch("src.core.config.settings.MASTER_DB_PATH", str(base_path / "master.duckdb"))
    mocker.patch("src.core.config.settings.JP_MASTER_DB_PATH", str(base_path / "jquants_master.duckdb"))
    mocker.patch("src.core.config.settings.JP_PRICES_DB_PATH", str(base_path / "jquants_prices.duckdb"))
    mocker.patch("src.core.config.settings.JP_FACTS_DB_PATH", str(base_path / "jquants_financials.duckdb"))
    
    # Mock API
    mocker.patch("jquantsapi.ClientV2")
    
    from src.core.migrations import MigrationManager
    MigrationManager.apply_migrations()
    
    return JPEngine(), base_path

def test_chaos_toxic_price_data(sharded_env):
    """Test that malformed records don't crash the whole ingestion."""
    engine, base_path = sharded_env
    
    toxic_data = pd.DataFrame([
        {"Date": "invalid", "Code": "XXXX", "Open": "NAN"}, # Invalid
        {"Date": "2026-05-01", "Code": "1301", "Open": 100, "Close": 105, "Volume": 1000} # Valid
    ])
    
    engine.ingest_prices(toxic_data, "chaos-session")
    
    # Verify: 1 valid record should be in prices shard
    with db_manager.connect(base_path / "prices.duckdb") as conn:
        count = conn.execute("SELECT count(*) FROM daily_prices").fetchone()[0]
        assert count == 1

def test_chaos_shard_file_missing(sharded_env, mocker):
    """Test behavior when a shard file is deleted mid-run."""
    engine, base_path = sharded_env
    
    # Delete the prices shard
    (base_path / "prices.duckdb").unlink()
    
    mock_prices = pd.DataFrame([
        {"Date": "2026-05-01", "Code": "1301", "Open": 100, "Close": 105, "Volume": 1000}
    ])
    
    # It should fail or auto-recreate depending on design.
    # Current design: MigrationManager runs once at JPEngine init.
    # If file missing later, DuckDB connect will create a BLANK file, 
    # but table won't exist -> should raise error.
    with pytest.raises(Exception, match="Table with name daily_prices does not exist"):
        engine.ingest_prices(mock_prices, "missing-shard-test")
