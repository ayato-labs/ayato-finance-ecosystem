import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

from src.service.csv_parser import get_csv_from_edinet


def test_retry_on_429():
    """
    Boundary Test: Verify exponential backoff when hitting 429 Rate Limit.
    Updated for urllib implementation.
    """
    with patch("urllib.request.urlopen") as mock_urlopen:
        # Mock 429 for the first 2 calls
        mock_429 = urllib.error.HTTPError(
            url="http://test", code=429, msg="Too Many Requests", hdrs={}, fp=None
        )

        # Mock 200 SUCCESS
        mock_response = MagicMock()
        mock_response.read.return_value = b"success"
        mock_response.__enter__.return_value = mock_response

        mock_urlopen.side_effect = [mock_429, mock_429, mock_response]

        with patch("time.sleep", return_value=None) as mock_sleep:
            content = get_csv_from_edinet("DOC_429", "key")

            assert content == b"success"
            assert mock_urlopen.call_count == 3
            assert mock_sleep.call_count == 2
            # Check wait times: 2^0=1, 2^1=2
            assert mock_sleep.call_args_list[0][0][0] == 1
            assert mock_sleep.call_args_list[1][0][0] == 2


def test_failure_after_max_retries():
    """
    Boundary Test: Ensure it gives up after max retries.
    """
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_429 = urllib.error.HTTPError(
            url="http://test", code=429, msg="Too Many Requests", hdrs={}, fp=None
        )
        mock_urlopen.side_effect = mock_429

        with patch("time.sleep", return_value=None):
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
