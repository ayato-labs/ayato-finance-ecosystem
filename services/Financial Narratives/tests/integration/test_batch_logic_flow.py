import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from src.batch_fetch import process_us_ticker
from src.storage import FinancialNarrativeStorage

@pytest.mark.asyncio
async def test_process_us_ticker_flow():
    # Setup mocks
    mock_fetcher = MagicMock()
    mock_parser = MagicMock()
    mock_storage = MagicMock()
    
    mock_fetcher.get_latest_submissions.return_value = {"filings": {"recent": {}}}
    mock_fetcher.filter_relevant_filings.return_value = [
        {"accessionNumber": "000-111", "filingDate": "2026-05-01", "primaryDocument": "doc.htm", "form": "10-Q"}
    ]
    mock_fetcher.get_cik.return_value = "0000320193"
    mock_storage.filing_exists.return_value = False
    
    # Mock requests.get inside asyncio.to_thread
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html>Filing Content</html>"
        mock_get.return_value = mock_resp
        
        mock_parser.extract_all_sections.return_value = {"business": "mocked text"}
        
        await process_us_ticker("AAPL", mock_fetcher, mock_parser, mock_storage, run_structuring=False, days=7)
        
        # Verify calls
        assert mock_storage.save_filing.called
        args, kwargs = mock_storage.save_filing.call_args
        metadata, sections = args
        assert metadata["accessionNumber"] == "000-111"
        assert sections["business"] == "mocked text"

@pytest.mark.asyncio
async def test_process_us_ticker_already_exists():
    mock_fetcher = MagicMock()
    mock_storage = MagicMock()
    
    mock_fetcher.get_latest_submissions.return_value = {"filings": {"recent": {}}}
    mock_fetcher.filter_relevant_filings.return_value = [
        {"accessionNumber": "EXIST-123", "filingDate": "2026-05-01", "primaryDocument": "doc.htm", "form": "10-Q"}
    ]
    mock_storage.filing_exists.return_value = True
    
    await process_us_ticker("AAPL", mock_fetcher, None, mock_storage, days=7)
    
    # Should skip download and parse
    assert not mock_storage.save_filing.called
