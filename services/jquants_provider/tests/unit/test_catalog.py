import pytest
import tempfile
from pathlib import Path
from src.core.catalog import CatalogManager
from src.core.db import db_manager

@pytest.fixture
def temp_catalog_db():
    """Fixture to provide a temporary catalog DB."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_master.duckdb"
        # We need a manager instance with this specific path
        # For simplicity, we can mock the settings or pass the path
        # Since CatalogManager uses settings.DB_MASTER_PATH, we'll patch it
        yield db_path

def test_catalog_update_and_get_status(mocker, temp_catalog_db):
    """Test updating and retrieving shard status from catalog."""
    mocker.patch("src.core.config.settings.MASTER_DB_PATH", str(temp_catalog_db))
    
    from src.core.catalog import catalog_manager
    
    # Update status
    catalog_manager.update_shard_status(
        shard_name="prices",
        table_name="daily_prices",
        last_session_id="session-123",
        last_date="20260505",
        record_count=100
    )
    
    # Verify
    status = catalog_manager.get_shard_status("prices", "daily_prices")
    assert status is not None
    assert status["last_session_id"] == "session-123"
    assert status["record_count"] == 100
    
    # Check non-existent
    none_status = catalog_manager.get_shard_status("unknown", "unknown")
    assert none_status is None
