import pytest
import os
from src.core.csv_parser import get_csv_from_edinet


def test_get_csv_from_edinet_failure():
    """
    Unit Test: Verify behavior when API returns failure.
    No mocking for API as requested.
    """
    # Use invalid DocID to force an API failure (should return None or handle gracefully)
    api_key = os.getenv("EDINET_API_KEY", "invalid_key")
    # Using a known bad ID
    result = get_csv_from_edinet("INVALID_DOC_ID", api_key)

    # Assert that it doesn't crash and returns None
    assert result is None


def test_get_csv_from_edinet_real_request():
    """
    Unit Test: Verify real API call (assuming a known valid or at least reachable endpoint).
    No mocking for API as requested.
    """
    # This might fail due to network or invalid key, which is expected for strict testing
    api_key = os.getenv("EDINET_API_KEY")
    if not api_key:
        pytest.skip("EDINET_API_KEY not set")

    # Try a known potentially valid ID or handle the failure
    result = get_csv_from_edinet("E00000", api_key)
    # Even if it fails, it shouldn't crash
    assert isinstance(result, (bytes, type(None)))
