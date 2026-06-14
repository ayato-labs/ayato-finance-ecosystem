import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

from src.datalake.service.csv_parser import get_csv_from_edinet


def test_retry_on_429():
    """
    Boundary Test: Verify exponential backoff when hitting 429 Rate Limit.
    Updated for urllib implementation.
    """
    current_time = [100.0]
    def mock_sleep_side_effect(secs):
        current_time[0] += secs

    with patch("urllib.request.urlopen") as mock_urlopen, \
         patch("time.monotonic", side_effect=lambda: current_time[0]), \
         patch("time.sleep", side_effect=mock_sleep_side_effect) as mock_sleep:
         
        # Mock 429 for the first 2 calls
        mock_429 = urllib.error.HTTPError(
            url="http://test", code=429, msg="Too Many Requests", hdrs={}, fp=None
        )

        # Mock 200 SUCCESS
        mock_response = MagicMock()
        mock_response.read.return_value = b"PK\x03\x04success"
        mock_response.__enter__.return_value = mock_response

        mock_urlopen.side_effect = [mock_429, mock_429, mock_response]

        content = get_csv_from_edinet("DOC_429", "key")

        assert content == b"PK\x03\x04success"
        assert mock_urlopen.call_count == 3
        assert mock_sleep.call_count == 2
        # Check wait times: should sleep for global backoff (around 60s)
        assert 58.0 <= mock_sleep.call_args_list[0][0][0] <= 60.0
        assert 58.0 <= mock_sleep.call_args_list[1][0][0] <= 60.0


def test_failure_after_max_retries():
    """
    Boundary Test: Ensure it gives up after max retries.
    """
    current_time = [100.0]
    def mock_sleep_side_effect(secs):
        current_time[0] += secs

    with patch("urllib.request.urlopen") as mock_urlopen, \
         patch("time.monotonic", side_effect=lambda: current_time[0]), \
         patch("time.sleep", side_effect=mock_sleep_side_effect) as mock_sleep:
         
        mock_429 = urllib.error.HTTPError(
            url="http://test", code=429, msg="Too Many Requests", hdrs={}, fp=None
        )
        mock_urlopen.side_effect = mock_429

        content = get_csv_from_edinet("DOC_FAIL", "key")
        assert content is None
        assert mock_urlopen.call_count == 3


def test_http_error_non_429():
    """
    Boundary Test: Non-429 errors should not retry and return None immediately.
    """
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_404 = urllib.error.HTTPError(
            url="http://test", code=404, msg="Not Found", hdrs={}, fp=None
        )
        mock_urlopen.side_effect = mock_404

        content = get_csv_from_edinet("DOC_404", "key")
        assert content is None
        assert mock_urlopen.call_count == 1
