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

def test_catalog_update_and_get_status(temp_catalog_db):
    """Test updating and retrieving shard status from catalog."""
    # Create a fresh manager for this test
    cm = CatalogManager(master_db_path=temp_catalog_db)
    
    # Update status
    cm.update_shard_status(
        shard_name="prices",
        file_path="data/prices.duckdb",
        version=1,
        status="active",
        records_count=100
    )
    
    # Verify
    info = cm.get_shard_info("prices")
    assert info is not None
    assert info["records_count"] == 100
    
    # Check non-existent
    none_status = cm.get_shard_info("unknown")
    assert none_status is None
