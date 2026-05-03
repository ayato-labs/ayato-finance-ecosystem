from datetime import date
from unittest.mock import MagicMock

import pytest

from src.edinet.sync_worker import EDINETSyncWorker


@pytest.fixture
def mock_client():
    client = MagicMock()
    # Mock document list
    client.get_document_list.return_value = {
        "results": [
            {
                "docID": "S_INT_001",
                "docTypeCode": "120",
                "filerName": "Integrator Corp",
                "docDescription": "Annual Report",
                "submissionPeriod": "2026-04-10",
            }
        ]
    }
    # Mock ZIP content
    client.download_document_csv.return_value = b"mock_zip_bytes"
    # Mock extraction
    client.extract_csv_from_zip.return_value = [
        (
            "test.csv",
            '要素ID\t"項目名"\t"コンテキストID"\t"ユニット"\t"値"\nj_cor:Sales\t"S"\t"C"\t"JPY"\t"5000"',
        )
    ]
    return client


def test_sync_worker_full_cycle(tmp_path, mock_client):
    db_file = tmp_path / "integration_sync.duckdb"
    worker = EDINETSyncWorker()
    worker.client = mock_client
    # Set storage to a temporary one
    worker.storage.db_path = str(db_file)
    worker.storage._init_db()

    target_date = date(2026, 4, 10)
    worker.sync_date(target_date)

    # Verify storage
    assert worker.storage.is_document_exists("S_INT_001")

    import duckdb

    with duckdb.connect(str(db_file)) as con:
        count = con.execute("SELECT COUNT(*) FROM raw_facts").fetchone()[0]
        assert count == 1
        val = con.execute("SELECT amount_value FROM raw_facts").fetchone()[0]
        assert val == 5000.0


def test_incremental_sync_skips_existing(tmp_path, mock_client):
    db_file = tmp_path / "incremental_sync.duckdb"
    worker = EDINETSyncWorker()
    worker.client = mock_client
    worker.storage.db_path = str(db_file)
    worker.storage._init_db()

    # Pre-save document
    worker.storage.save_document({"docID": "S_INT_001", "submissionPeriod": "2026-04-10"})

    worker.sync_date(date(2026, 4, 10))

    # client.download_document_csv should NOT be called because it exists
    mock_client.download_document_csv.assert_not_called()
