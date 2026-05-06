import time
import pytest
import requests
from unittest.mock import MagicMock, patch
from src.core.csv_parser import get_csv_from_edinet

def test_retry_on_429():
    """
    Boundary Test: Verify exponential backoff when hitting 429 Rate Limit.
    """
    with patch("requests.get") as mock_get:
        # Mock 429 for the first 2 calls, then 200 SUCCESS
        mock_429 = MagicMock()
        mock_429.status_code = 429
        
        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.content = b"success"
        
        mock_get.side_effect = [mock_429, mock_429, mock_200]
        
        # We also mock time.sleep to make the test run instantly
        with patch("time.sleep", return_value=None) as mock_sleep:
            content = get_csv_from_edinet("DOC_429", "key", max_retries=5)
            
            assert content == b"success"
            assert mock_get.call_count == 3
            assert mock_sleep.call_count == 2
            # Check wait times: 2^0=1, 2^1=2
            assert mock_sleep.call_args_list[0][0][0] == 1
            assert mock_sleep.call_args_list[1][0][0] == 2

def test_failure_after_max_retries():
    """
    Boundary Test: Ensure it gives up after max retries.
    """
    with patch("requests.get") as mock_get:
        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_get.return_value = mock_429
        
        with patch("time.sleep", return_value=None):
            content = get_csv_from_edinet("DOC_FAIL", "key", max_retries=3)
            assert content is None
            assert mock_get.call_count == 3

def test_logical_error_in_200_body():
    """
    Boundary Test: Some APIs return 200 OK but with error JSON in body.
    """
    with patch("requests.get") as mock_get:
        mock_error_body = MagicMock()
        mock_error_body.status_code = 200
        mock_error_body.content = b'{"statusCode": "429", "message": "Rate limit exceeded"}'
        mock_get.return_value = mock_error_body
        
        with patch("time.sleep", return_value=None):
            # This should trigger the retry logic if we implemented the body check
            content = get_csv_from_edinet("DOC_LOGICAL", "key", max_retries=2)
            assert content is None # Since it retried and eventually failed/returned None
