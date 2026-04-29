import io
import zipfile
from datetime import date
from unittest.mock import MagicMock, patch

import duckdb

from src.edinet.sync_worker import EDINETSyncWorker


def create_mock_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        # Mock EDINET CSV content
        csv_content = "tag1,name1,ctx1,unit1,100\ntag2,name2,ctx2,unit2,200".encode("utf-16")
        z.writestr("test_financial_data.csv", csv_content)
    return buf.getvalue()


@patch("requests.get")
def test_edinet_full_system_flow(mock_get, tmp_path):
    # Setup temp DB path for the worker
    test_db = tmp_path / "system_edinet.duckdb"

    # Mocking the Doc List API
    mock_doc_list = MagicMock()
    mock_doc_list.status_code = 200
    mock_doc_list.json.return_value = {
        "results": [
            {
                "docID": "SYS_DOC_1",
                "docTypeCode": "120",  # Relevant
                "filerName": "System Corp",
                "docDescription": "Annual Report",
                "submissionPeriod": "2023-01-01",
            },
            {
                "docID": "SYS_DOC_2",
                "docTypeCode": "999",  # Irrelevant
                "filerName": "Other Corp",
            },
        ]
    }

    # Mocking the ZIP Download API
    mock_zip = MagicMock()
    mock_zip.status_code = 200
    mock_zip.content = create_mock_zip()

    # Sequential returns for mock_get
    mock_get.side_effect = [mock_doc_list, mock_zip]

    # Initialize worker with test DB
    with patch("src.edinet.storage.EDINETStorage.__init__", lambda s, db_path=None: None):
        from src.edinet.storage import EDINETStorage

        storage = EDINETStorage()
        storage.db_path = str(test_db)
        storage._init_db()

        worker = EDINETSyncWorker()
        worker.storage = storage

        # Execute Sync
        worker.sync_date(date(2023, 1, 1))

        # Assertions
        with duckdb.connect(str(test_db)) as con:
            # Should have 1 document (SYS_DOC_1)
            docs = con.execute("SELECT doc_id, filer_name FROM documents").fetchall()
            assert len(docs) == 1
            assert docs[0][0] == "SYS_DOC_1"

            # Should have 2 facts
            facts = con.execute("SELECT amount_value FROM raw_facts").fetchall()
            assert len(facts) == 2
            assert facts[0][0] == 100.0
            assert facts[1][0] == 200.0
