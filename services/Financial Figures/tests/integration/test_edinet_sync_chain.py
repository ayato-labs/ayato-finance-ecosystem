import io
import zipfile
from datetime import date

import pytest

from src.edinet.storage import EDINETStorage
from src.edinet.sync_worker import EDINETSyncWorker


@pytest.fixture
def sync_worker(tmp_path):
    db_file = tmp_path / "sync_chain.duckdb"
    worker = EDINETSyncWorker()
    worker.storage = EDINETStorage(db_path=str(db_file))
    return worker


def test_sync_date_chain_success(sync_worker, mocker):
    """Verify that sync_date correctly processes a document from listing to storage."""
    # 1. Mock Document List
    mock_doc_list = {
        "metadata": {"resultCode": "200"},
        "results": [
            {
                "docID": "S100TEST",
                "docTypeCode": "120",  # Annual Report
                "filerName": "Chain Test Corp",
                "docDescription": "Financial Statements",
                "edinetCode": "E99999",
                "submissionPeriod": "2026-04-20",
            }
        ],
    }
    mocker.patch(
        "src.edinet.client.requests.get",
        side_effect=[
            mocker.Mock(
                status_code=200,
                json=lambda: mock_doc_list,
                headers={"Content-Type": "application/json"},
            ),
            # 2. Mock ZIP download
            mocker.Mock(
                status_code=200,
                content=create_mock_zip(),
                headers={"Content-Type": "application/octet-stream"},
            ),
        ],
    )

    # 3. Execute
    sync_worker.sync_date(date(2026, 4, 20))

    # 4. Verify Storage
    assert sync_worker.storage.is_document_exists("S100TEST")
    # Verify raw facts were saved
    import duckdb

    with duckdb.connect(sync_worker.storage.db_path) as conn:
        count = conn.execute("SELECT count(*) FROM raw_facts WHERE doc_id='S100TEST'").fetchone()[0]
        assert count > 0


def create_mock_zip():
    """Create a valid ZIP in memory containing a CSV."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        header = "要素ID\t項目名\tコンテキストID\tユニットID\t単位\t値\n"
        row = "jpcrp_cor:NetSales\t売上高\tCurrentYear\tJPY\t円\t123456\n"
        csv_content = header + row
        z.writestr("test.csv", csv_content.encode("utf-16"))
    return buf.getvalue()
