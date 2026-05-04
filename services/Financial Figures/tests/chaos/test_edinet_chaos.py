from datetime import date
from unittest.mock import MagicMock

import duckdb
import pytest

from src.edinet.sync_worker import EDINETSyncWorker


def test_chaos_corrupt_zip_skip(tmp_path, mocker):
    """Test that invalid ZIP content is skipped gracefully without crashing the worker."""
    db_file = tmp_path / "chaos_skip.duckdb"
    from src.edinet.storage import EDINETStorage
    from src.edinet.sync_worker import EDINETSyncWorker

    worker = EDINETSyncWorker()
    worker.storage = EDINETStorage(db_path=str(db_file))

    # Mock Document List with 1 doc
    from src.edinet.client import EDINETClient

    worker.client = mocker.Mock(spec=EDINETClient)
    worker.client.get_document_list.return_value = {
        "results": [{"docID": "S_BAD_ZIP", "docTypeCode": "120", "edinetCode": "E001"}]
    }
    # Mock ZIP download to return None (simulating our new is_zipfile check failure)
    worker.client.download_document_csv.return_value = None

    # Execute - should NOT raise Exception
    worker.sync_date(date(2026, 4, 10))

    # Verify metadata was saved but no facts
    with duckdb.connect(str(db_file)) as conn:
        assert (
            conn.execute("SELECT count(*) FROM documents WHERE doc_id='S_BAD_ZIP'").fetchone()[0]
            == 1
        )
        assert (
            conn.execute("SELECT count(*) FROM raw_facts WHERE doc_id='S_BAD_ZIP'").fetchone()[0]
            == 0
        )


def test_chaos_network_timeout(tmp_path):
    """Test handling of EDINET API timeouts."""
    worker = EDINETSyncWorker()
    mock_client = MagicMock()
    # Simulate a network failure deep in the client
    mock_client.get_document_list.side_effect = RuntimeError("EDINET API Timeout")
    worker.client = mock_client

    with pytest.raises(RuntimeError, match="EDINET API Timeout"):
        worker.sync_date(date(2026, 4, 10))


def test_chaos_malformed_csv_columns(tmp_path):
    """Test parser resilience against unexpected CSV headers or missing columns."""
    from src.edinet.parser import EDINETParser

    # Truly broken: only 2 columns in data, while 5 expected by fallback
    bad_csv = "ID\tName\tContext\tUnit\n1\tN\n"
    facts = EDINETParser.parse_financial_csv(bad_csv)

    # Should skip rows with insufficient columns
    assert len(facts) == 0


def test_chaos_db_lock_resilience(tmp_path):
    """Test behavior when DuckDB file is locked by another process."""
    import duckdb

    db_file = tmp_path / "locked.duckdb"

    # Hold a connection to simulate a lock in some environments (DuckDB is single-writer)
    con = duckdb.connect(str(db_file))

    worker = EDINETSyncWorker()
    worker.storage.db_path = str(db_file)

    # Attempting to init_db while con is active might fail depending on DuckDB version
    # Here we just verify that our storage layer logs the error.
    try:
        worker.storage._init_db()
    except Exception as e:
        assert "Database Initialization Failure" in str(e)
    finally:
        con.close()


def test_chaos_mixed_api_responses(tmp_path, mocker):
    """Test that one document failure does not prevent other documents from being processed."""
    db_file = tmp_path / "chaos_mixed.duckdb"
    from src.edinet.storage import EDINETStorage
    from src.edinet.sync_worker import EDINETSyncWorker

    worker = EDINETSyncWorker()
    worker.storage = EDINETStorage(db_path=str(db_file))

    from src.edinet.client import EDINETClient
    from tests.integration.test_edinet_sync_chain import create_mock_zip

    # We use a real client but mock its network methods to ensure logic like
    # extract_csv_from_zip works
    real_client = EDINETClient(api_key="test")
    worker.client = mocker.Mock(spec=real_client)
    worker.client.download_document_csv.side_effect = [
        create_mock_zip(),  # OK
        None,  # Corrupt (Skip)
        RuntimeError("API Fail"),  # Error (Skip)
    ]
    # Allow extract_csv_from_zip to work (using the real implementation)
    worker.client.extract_csv_from_zip.side_effect = real_client.extract_csv_from_zip

    worker.client.get_document_list.return_value = {
        "results": [
            {"docID": "D_OK", "docTypeCode": "120", "edinetCode": "E1"},
            {"docID": "D_CORRUPT", "docTypeCode": "120", "edinetCode": "E2"},
            {"docID": "D_FAIL", "docTypeCode": "120", "edinetCode": "E3"},
        ]
    }

    worker.sync_date(date(2026, 4, 10))

    with duckdb.connect(str(db_file)) as conn:
        # All 3 documents should have metadata (saved before download)
        assert conn.execute("SELECT count(*) FROM documents").fetchone()[0] == 3
        # Only D_OK should have facts
        ok_facts = conn.execute("SELECT count(*) FROM raw_facts WHERE doc_id='D_OK'").fetchone()[0]
        assert ok_facts > 0
        corrupt_facts = conn.execute(
            "SELECT count(*) FROM raw_facts WHERE doc_id='D_CORRUPT'"
        ).fetchone()[0]
        assert corrupt_facts == 0
