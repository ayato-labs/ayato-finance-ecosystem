import io
import zipfile

from src.datalake.service.csv_parser import parse_edinet_csv


def test_parse_edinet_csv_valid():
    """Unit: Parse a valid ZIP with a CSV file."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        csv_content = "header\ncol1,col2,col3,col4,col5,col6,col7,col8,col9\n1,2,3,4,5,6,7,8,100"
        zip_file.writestr("test.csv", csv_content)

    results = parse_edinet_csv(zip_buffer.getvalue())
    assert "test.csv" in results
    df = results["test.csv"]
    assert not df.empty
    # skiprows=1 means col1,col2... is the header
    assert df.columns[8] == "col9"


def test_parse_edinet_csv_empty_zip():
    """Severe Test: Handle empty ZIP archives gracefully."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as _:
        # Create an empty zip file by just closing the context
        pass

    results = parse_edinet_csv(zip_buffer.getvalue())
    assert results == {}


def test_parse_edinet_csv_bad_zip():
    """Severe Test: Handle corrupted ZIP data."""
    results = parse_edinet_csv(b"not a zip")
    assert results == {}
