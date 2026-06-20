import pytest
from unittest.mock import MagicMock, patch
from datetime import date
from edgar_provider.fetcher import EdgarFetcher

@pytest.fixture
def fetcher():
    return EdgarFetcher(user_agent="test-agent test@example.com")

def test_fetcher_init(fetcher):
    assert fetcher.headers["User-Agent"] == "test-agent test@example.com"

@patch("requests.get")
def test_request_with_retry_success(mock_get, fetcher):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response
    
    resp = fetcher._request_with_retry("http://example.com")
    assert resp.status_code == 200
    assert mock_get.call_count == 1

@patch("requests.get")
def test_list_daily_filings(mock_get, fetcher):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = """Central Index Key|Entity Name|Form Type|Date Filed|Filename
--------------------------------------------------------------------------------
0000320193|Apple Inc.|10-K|2026-06-15|edgar/data/320193/0000320193-26-000001.txt
"""
    mock_get.return_value = mock_response
    
    # Mock ticker map to avoid extra requests
    fetcher.cik_to_ticker_map = {"0000320193": "AAPL"}
    
    results = fetcher.list_daily_filings(date(2026, 6, 15))
    assert len(results) == 1
    assert results[0]["ticker"] == "AAPL"
    assert results[0]["form"] == "10-K"
    assert results[0]["accessionNumber"] == "0000320193-26-000001"
