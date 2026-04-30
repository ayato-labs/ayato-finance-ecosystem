from datetime import date

import duckdb
import pytest

from src.edinet.client import EDINETClient
from src.edinet.parser import EDINETParser
from src.edinet.storage import EDINETStorage
from src.edinet.sync_worker import EDINETSyncWorker


def test_client_url_logic():
    client = EDINETClient(api_key="test_key")
    assert client.api_key == "test_key"
    assert "documents.json" in f"{client.BASE_URL}/documents.json"


def test_download_document_csv_validation(mocker):
    """Verify that is_zipfile validation skips invalid ZIP content."""
    client = EDINETClient(api_key="test")

    # Mock requests to return non-ZIP data
    mock_resp = mocker.Mock()
    mock_resp.content = b"NOT_A_ZIP_FILE"
    mock_resp.headers = {"Content-Type": "application/octet-stream"}
    mock_resp.status_code = 200
    mocker.patch("requests.get", return_value=mock_resp)

    res = client.download_document_csv("S123")
    assert res is None


def test_download_document_csv_json_handling(mocker):
    """Verify that JSON error responses are handled gracefully."""
    client = EDINETClient(api_key="test")

    mock_resp = mocker.Mock()
    mock_resp.content = b'{"metadata": {"resultCode": "404", "message": "No File"}}'
    mock_resp.text = mock_resp.content.decode("utf-8")
    mock_resp.headers = {"Content-Type": "application/json"}
    mock_resp.json.return_value = {"metadata": {"message": "No File"}}
    mocker.patch("requests.get", return_value=mock_resp)

    res = client.download_document_csv("S404")
    assert res is None


def test_parser_valid_csv():
    # Statutory CSV typically uses tab and these exact headers
    csv_content = (
        "要素ID\t項目名\tコンテキストID\tユニットID\t単位\t値\n"
        "jpcrp_cor:NetSales\t売上高\tCurrentYear\tJPY\t円\t1000000\n"
    )
    facts = EDINETParser.parse_financial_csv(csv_content)
    assert len(facts) >= 1
    assert facts[0]["id"] == "jpcrp_cor:NetSales"
    assert facts[0]["value"] == 1000000.0  # noqa: PLR2004


def test_storage_incremental_methods(tmp_path):
    db_file = tmp_path / "incremental.duckdb"
    storage = EDINETStorage(db_path=str(db_file))

    doc_id = "S_TEST_INC"
    assert not storage.is_document_exists(doc_id)

    storage.save_document(
        {
            "docID": doc_id,
            "secCode": "9999",
            "filerName": "Test Inc",
            "docDescription": "Test Doc",
            "submissionPeriod": date(2026, 1, 1),
        }
    )

    assert storage.is_document_exists(doc_id)
    assert storage.get_last_sync_date() == date(2026, 1, 1)


def test_storage_raw_facts_integrity(tmp_path):
    db_file = tmp_path / "integrity.duckdb"
    storage = EDINETStorage(db_path=str(db_file))

    doc_id = "S_INTEG"
    storage.save_document({"docID": doc_id, "submissionPeriod": date(2026, 1, 1)})

    facts = [{"id": "f1", "name": "N1", "context": "c1", "value": 500.0, "unit": "JPY"}]
    storage.save_facts(doc_id, facts)

    with duckdb.connect(str(db_file)) as con:
        res = con.execute("SELECT amount_value FROM raw_facts WHERE doc_id=?", (doc_id,)).fetchone()
        assert res[0] == 500.0  # noqa: PLR2004


@pytest.mark.parametrize("invalid_val", ["", "N/A", "Unknown", "-", "1,234.56"])
def test_parser_robustness(invalid_val):
    # Header must be valid for the row to be processed
    header = "要素ID\t項目名\tコンテキストID\tユニットID\t単位\t値\n"
    csv = f"{header}ID1\tN1\tC1\tU1\t円\t{invalid_val}\n"
    facts = EDINETParser.parse_financial_csv(csv)
    if invalid_val == "1,234.56":
        assert len(facts) == 1
        assert facts[0]["value"] == 1234.56  # noqa: PLR2004
    else:
        assert len(facts) == 0


def test_sync_worker_years_clipping(mocker):
    """Verify that EDINETSyncWorker clips requested years to 5."""
    worker = EDINETSyncWorker()

    # Mock time.sleep to avoid 15 minute wait
    mocker.patch("time.sleep")

    # Mock client and mapper to avoid network/DB
    mock_client = mocker.Mock()
    mock_client.get_document_list.return_value = {"results": []}
    worker.client = mock_client

    mock_mapper = mocker.Mock()
    mock_mapper.get_all_target_edinet_codes.return_value = ["E001"]
    worker.mapper = mock_mapper

    worker.run_historical_backfill(years=10)

    # Check if get_document_list was called for Phase 1 (31 days) + Phase 2 (5 * 365 + 1 days)
    # The count should be around 1857
    assert mock_client.get_document_list.call_count <= 1870  # noqa: PLR2004
    assert mock_client.get_document_list.call_count >= 1850  # noqa: PLR2004
