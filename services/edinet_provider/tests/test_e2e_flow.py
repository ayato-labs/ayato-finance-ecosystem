import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from src.core.db import db_manager

def test_full_sync_flow_with_db_verification(engine, mocker):
    """
    Comprehensive Test: Run sync using replayed API data and verify DB state.
    """
    # Force TESTING environment
    mocker.patch.dict("os.environ", {"TESTING": "true"})

    # 1. Setup Mock API Data
    fixture_path = Path("tests/fixtures/edinet_replay.json")
    with open(fixture_path, "r", encoding="utf-8") as f:
        replayed_data = json.load(f)

    # Mock Document objects
    mock_docs = []
    for item in replayed_data:
        doc = MagicMock()
        doc._data = item
        doc.doc_id = item.get("docID", "unknown")
        # Text blocks for narrative extraction
        mock_report = MagicMock()
        mock_report.text_blocks = {"BusinessRisksTextBlock": "Test Risk Content"}
        doc.parse.return_value = mock_report
        mock_docs.append(doc)

    # Mock entity.documents
    mock_entity = mocker.patch("edinet_tools.entity")
    mock_entity.return_value.documents.return_value = mock_docs

    ticker = "7203"
    session_id = "e2e-replay-test"

    # 2. Run Sync
    # In-memory DB is already initialized by fixture 'engine'
    engine.sync_company(ticker, days=365, session_id=session_id)

    # 3. Verify Database State
    with db_manager.connect_master() as conn:
        # Check if table exists (it might be in 'main' for in-memory)
        # Use info_schema to find the actual table
        tables = [row[0] for row in conn.execute("SELECT table_name FROM information_schema.tables").fetchall()]
        print(f"DEBUG: Tables found in memory: {tables}")
        
        # Determine the table name (might be registry_db.filings or just filings)
        target_table = "filings" if "filings" in tables else "registry_db.filings"
        
        filings_count = conn.execute(f"SELECT count(*) FROM {target_table}").fetchone()[0]
        assert filings_count > 0
        
        # Verify specific record
        doc_id = replayed_data[0]["docID"]
        res = conn.execute(f"SELECT filer_name FROM {target_table} WHERE doc_id = '{doc_id}'").fetchone()
        assert res[0] == replayed_data[0]["filerName"]
