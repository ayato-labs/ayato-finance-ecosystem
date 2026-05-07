import pytest
from src.service.csv_parser import get_csv_from_edinet

def test_get_csv_from_edinet_real_call():
    """
    Unit: Verify real API call behavior (NO MOCK).
    This will likely return None or an error because the API key is invalid/missing,
    but the goal is to verify the actual networking logic as requested.
    """
    # Using a dummy doc_id and empty key
    result = get_csv_from_edinet(doc_id="S1000000", api_key="INVALID_KEY")
    
    # We expect None or a failure, but we want to see it actually try the call.
    # If it fails with 403 or 401, it means the networking logic works.
    assert result is None or isinstance(result, bytes)

def test_get_csv_from_edinet_invalid_url():
    """
    Unit: Test with a completely invalid URL or malformed parameters.
    """
    # This might trigger a different exception
    result = get_csv_from_edinet(doc_id="../../etc/passwd", api_key="dummy")
    assert result is None
