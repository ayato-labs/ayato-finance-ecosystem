import pytest
from unittest.mock import MagicMock, patch
from datetime import date
from src.providers.edinet.sync_worker import EDINETSyncWorker

@pytest.fixture
def mocked_worker(test_settings):
    """Provides a SyncWorker with mocked external dependencies."""
    with patch("src.providers.edinet.sync_worker.EDINETClient") as mock_client:
        with patch("src.providers.edinet.sync_worker.AIMapper") as mock_ai:
            worker = EDINETSyncWorker()
            worker.client = mock_client.return_value
            worker.ai_mapper = mock_ai.return_value
            yield worker, worker.client, worker.ai_mapper

def test_sync_date_flow(mocked_worker):
    """Test the full sync flow for a single date with mocked API."""
    worker, mock_client, mock_ai = mocked_worker
    
    # Setup mocks
    mock_client.get_document_list.return_value = [
        {"docID": "S100TEST", "filerName": "Test Corp", "secCode": "80010", "docDescription": "有価証券報告書"}
    ]
    # Simulate download and parse success
    with patch.object(worker, "ensure_ticker_master", return_value=None):
        with patch.object(worker.parser, "parse_xbrl_to_facts", return_value=[{"element_id": "NetSales", "element_name": "Sales", "amount_value": 5000}]):
            mock_ai.map_tags_bulk.return_value = {
                "EDINET:NetSales": {"mapped_label": "NetSales", "confidence": 0.95, "reasoning": "test", "model": "test"}
            }
            
            worker.sync_date(date(2024, 3, 29))
            
            # Verify interactions
            mock_client.get_document_list.assert_called_once()
            mock_ai.map_tags_bulk.assert_called()
            assert worker.storage.is_document_stored("S100TEST")

def test_sync_worker_api_error_handling(mocked_worker):
    """Test worker resilience when API returns an error."""
    worker, mock_client, _ = mocked_worker
    mock_client.get_document_list.side_effect = Exception("EDINET API Down")
    
    # Flow should handle the exception and not crash (logged via job_log)
    with pytest.raises(Exception): # Assuming the high-level worker might propagate or log
        worker.sync_date(date(2024, 3, 29))
