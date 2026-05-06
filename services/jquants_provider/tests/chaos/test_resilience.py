import pytest
import pandas as pd
from src.engine import JPEngine
from tenacity import RetryError

@pytest.fixture
def mock_engine(mocker):
    mocker.patch("jquantsapi.ClientV2")
    engine = JPEngine()
    # Speed up retries for testing
    # We patch the retry decorator's wait/stop if needed, 
    # but easier to patch time.sleep
    mocker.patch("time.sleep", return_value=None)
    return engine

def test_api_429_retry_success(mock_engine, mocker):
    """Verify that we retry on 429 and succeed if the next call is 200."""
    # ClientV2 uses get_eq_bars_daily
    mock_call = mocker.patch.object(mock_engine.cli, "get_eq_bars_daily")
    
    # 1. First call fails with 429, second succeeds
    mock_call.side_effect = [
        Exception("too many 429 error responses"),
        pd.DataFrame([{"Code": "1301", "Date": "2026-05-01", "Open": 100}])
    ]
    
    # This calls fetch_daily_bars which has @retry
    df = mock_engine.fetch_daily_bars("20260501")
    
    assert len(df) == 1
    assert mock_call.call_count == 2

def test_api_fatal_failure_after_retries(mock_engine, mocker):
    """Verify that we eventually give up after max retries."""
    mock_call = mocker.patch.object(mock_engine.cli, "get_eq_bars_daily")
    
    # All calls fail
    mock_call.side_effect = Exception("Permanent 500 error")
    
    # We expect the error to bubble up after retries
    with pytest.raises(Exception, match="Permanent 500 error"):
        mock_engine.fetch_daily_bars("20260501")
    
    assert mock_call.call_count == 5 # Default stop_after_attempt(5)
