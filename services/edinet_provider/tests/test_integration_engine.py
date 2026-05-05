import pytest
from unittest.mock import MagicMock
from src.engine import JPEDINETEngine

def test_sync_company_mocked(mocker):
    """
    Integration Test: Verify functional flow with mocked API.
    """
    # Mock dependencies
    mock_entity = mocker.patch("edinet_tools.entity")
    mock_doc = MagicMock()
    mock_doc._data = {
        "docID": "S100TEST",
        "edinetCode": "E00000",
        "filerName": "Test Corp",
        "docDescription": "Test Report",
        "submitDateTime": "2026-05-05 10:00:00",
        "formCode": "030000",
        "docTypeCode": "120",
        "csvFlag": "0" # Disable CSV part for simplicity
    }
    mock_entity.return_value.documents.return_value = [mock_doc]
    
    # Mock DB connection to avoid real DB access
    mocker.patch("src.core.db.db_manager.connect")
    # Mock migration manager
    mocker.patch("src.core.migrations.MigrationManager.apply_migrations")
    
    # Run engine
    engine = JPEDINETEngine()
    engine.sync_company("TEST", days=1, session_id="test-session")
    
    # Verify metadata was called
    assert mock_entity.called
