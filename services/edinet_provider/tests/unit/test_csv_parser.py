import io
import zipfile
import pandas as pd
from src.core.csv_parser import parse_edinet_csv

def test_parse_edinet_csv_valid():
    """
    Unit Test: Verify CSV parsing logic with a synthetic ZIP containing Shift-JIS encoded CSV.
    No mocking of external APIs here (pure logic).
    """
    # 1. Create a dummy CSV in Shift-JIS
    csv_content = "item_id,item_name,v1,v2,v3,v4,v5,unit,value\n1,Sales,x,x,x,x,x,JPY,1000\n2,Profit,x,x,x,x,x,JPY,200"
    encoded_csv = csv_content.encode("shift-jis")
    
    # 2. Create a dummy ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as z:
        z.writestr("test_facts.csv", encoded_csv)
    
    # 3. Parse
    results = parse_edinet_csv(zip_buffer.getvalue())
    
    # 4. Assertions
    assert "test_facts.csv" in results
    df = results["test_facts.csv"]
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert df.iloc[0, 1] == "Sales"
    assert str(df.iloc[0, 8]) == "1000"

def test_parse_edinet_csv_empty_zip():
    """Verify handling of empty or invalid content."""
    assert parse_edinet_csv(None) == {}
    assert parse_edinet_csv(b"not a zip") == {}

def test_parse_edinet_csv_no_csv_files():
    """Verify handling of ZIP with no CSV files."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as z:
        z.writestr("test.txt", b"just a text file")
    
    results = parse_edinet_csv(zip_buffer.getvalue())
    assert results == {}
