import pytest
import pandas as pd
import tempfile
from pathlib import Path
from src.engine import JPEngine
from src.core.db import db_manager
from src.core.catalog import catalog_manager

@pytest.fixture
def test_env(mocker):
    """Setup a multi-shard test environment."""
    tmpdir = tempfile.TemporaryDirectory()
    base_path = Path(tmpdir.name)
    
    # Patch all shard paths to use temp directory
    mocker.patch("src.core.config.settings.DATA_DIR", base_path)
    # Patch specific shard paths for safety
    mocker.patch("src.core.config.settings.MASTER_DB_PATH", str(base_path / "jquants_master.duckdb"))
    mocker.patch("src.core.config.settings.JP_MASTER_DB_PATH", str(base_path / "jquants_master_jp.duckdb"))
    mocker.patch("src.core.config.settings.JP_PRICES_DB_PATH", str(base_path / "jquants_prices_jp.duckdb"))
    mocker.patch("src.core.config.settings.JP_FACTS_DB_PATH", str(base_path / "jquants_financials_jp.duckdb"))
    
    # Mock API
    mocker.patch("jquantsapi.ClientV2")
    
    engine = JPEngine()
    # Initialize all shards
    from src.core.migrations import MigrationManager
    MigrationManager.apply_migrations()
    
    yield engine, base_path
    tmpdir.cleanup()

def test_multi_shard_ingestion_flow(test_env, mocker):
    """
    Test that data is correctly routed to different shards and tracked in catalog.
    """
    engine, base_path = test_env
    
    # 1. Setup mock data for prices
    mock_prices = pd.DataFrame([
        {"Date": "2026-05-01", "Code": "1301", "Open": 100, "Close": 105, "Volume": 1000}
    ])
    
    # 2. Setup mock data for financials
    mock_facts = pd.DataFrame([
        {
            "DisclosedDate": "2026-05-01", "DisclosedTime": "15:00", 
            "LocalCode": "1301", "DisclosureNumber": "A", "Type": "B",
            "FiscalYear": "2026", "FiscalPeriod": "Q1", "NetSales": 1000
        }
    ])
    
    # 3. Ingest
    session_id = "integration-test"
    engine.ingest_prices(mock_prices, session_id)
    engine.ingest_financials(mock_facts, session_id)
    
    # 4. Verify physical files
    # Prices shard should have data
    with db_manager.connect(base_path / "jquants_prices.duckdb") as conn:
        count = conn.execute("SELECT count(*) FROM daily_prices").fetchone()[0]
        assert count == 1
        
    # Financials shard should have data
    with db_manager.connect(base_path / "jquants_financials.duckdb") as conn:
        count = conn.execute("SELECT count(*) FROM company_facts").fetchone()[0]
        assert count == 1
        
    # 5. Verify Catalog
    status = catalog_manager.get_shard_status("prices", "daily_prices")
    assert status["last_session_id"] == session_id
    assert status["record_count"] == 1
