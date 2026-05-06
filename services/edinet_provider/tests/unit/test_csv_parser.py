import pytest
import io
import zipfile
import pandas as pd
from src.core.csv_parser import parse_edinet_csv, get_csv_from_edinet
from src.core.config import settings

def test_parse_edinet_csv_valid():
    """Test parsing a valid ZIP with a CSV inside."""
    # Create a dummy ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        # skiprows=1 is used, so the first row is skipped. 
        # The second row becomes the header.
        # The third row becomes the data.
        csv_content = (
            "Comment/Metadata Row (skipped)\n"
            "Col1,Col2,Col3,Col4,Col5,Col6,Col7,Col8,ValueCol\n"
            "Item1,Value1,Unit1,Context1,FY,Period,Extra,Extra,999"
        )
        zip_file.writestr("test.csv", csv_content)
    
    results = parse_edinet_csv(zip_buffer.getvalue())
    assert "test.csv" in results
    df = results["test.csv"]
    assert not df.empty
    # Value is in the 9th column (index 8)
    assert df.iloc[0, 8] == 999

def test_parse_edinet_csv_empty_zip():
    """Severe Test: Handle empty ZIP archives gracefully."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        pass
    
    results = parse_edinet_csv(zip_buffer.getvalue())
    assert results == {}

def test_parse_edinet_csv_corrupt_data():
    """Severe Test: Handle completely corrupt non-ZIP data."""
    results = parse_edinet_csv(b"not a zip file at all")
    assert results == {}

def test_get_csv_from_edinet_no_mock():
    """
    Unit Test (No Mock): Calls the real EDINET API.
    Note: This requires a valid API key in settings.
    If the key is invalid or missing, it should handle the 403/401 gracefully.
    """
    if not settings.EDINET_API_KEY:
        pytest.skip("EDINET_API_KEY not set, skipping live API test.")
    
    # Using a likely invalid/expired doc_id to test error handling logic without massive download
    result = get_csv_from_edinet("S0000000", settings.EDINET_API_KEY, max_retries=1)
    # Even if it's None (due to invalid ID), it shouldn't crash
    assert result is None or isinstance(result, bytes)

def test_get_csv_from_edinet_invalid_key():
    """Severe Test: Handle invalid API key without crashing."""
    result = get_csv_from_edinet("S100TEST", "INVALID_KEY", max_retries=1)
    assert result is None
