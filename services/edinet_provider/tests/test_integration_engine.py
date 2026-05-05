from unittest.mock import MagicMock
import pytest
from src.engine import JPEDINETEngine

def test_sync_company_mocked(mocker):
    """
    Integration Test: Verify functional flow with mocked API.
    """
    # Force TESTING environment to use :memory: DB which doesn't need ATTACH logic
    mocker.patch.dict("os.environ", {"TESTING": "true"})

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
        "csvFlag": "0",
    }
    mock_entity.return_value.documents.return_value = [mock_doc]

    # Initialize engine (will use in-memory DB due to TESTING=true)
    engine = JPEDINETEngine()
    engine.sync_company("TEST", days=1)

    # Verify that the entity was called
    mock_entity.assert_called_once_with("TEST")
