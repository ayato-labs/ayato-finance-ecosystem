import json
from pathlib import Path
from unittest.mock import MagicMock
from src.core.db import db_manager


def test_full_sync_flow_with_db_verification(engine, db, mocker):
    """
    Comprehensive Test: Run sync using replayed API data and verify DB state.
    """
    # 1. Setup Mock API Data
    fixture_path = Path("tests/fixtures/edinet_replay.json")
    with open(fixture_path, "r", encoding="utf-8") as f:
        replayed_data = json.load(f)

    # Mock Document objects
    mock_docs = []
    for item in replayed_data:
        doc = MagicMock()
        doc._data = item
        # Ensure doc.doc_id is accessible as engine uses it for error logging
        doc.doc_id = item.get("docID", "unknown")
        # Ensure parse returns a mock report that has 'business' attribute
        mock_report = MagicMock()
        mock_report.business = MagicMock()
        doc.parse.return_value = mock_report
        mock_docs.append(doc)

    # Mock entity.documents
    mock_entity = mocker.patch("edinet_tools.entity")
    mock_entity.return_value.documents.return_value = mock_docs

    ticker = "7203"
    session_id = "e2e-replay-test"

    # 2. Clear existing data for this session
    with db_manager.connect(engine.db_path) as conn:
        conn.execute("DELETE FROM filings WHERE session_id = ?", [session_id])

    # 3. Run sync
    # Use replayed data
    engine.sync_company(ticker, days=365, session_id=session_id)

    # 4. Verify DB state
    with db_manager.connect(engine.db_path) as conn:
        result = conn.execute(
            "SELECT count(*) FROM filings WHERE session_id = ?", [session_id]
        ).fetchone()[0]

        assert result > 0, "No data found in filings"
        assert result <= len(replayed_data)

        row = conn.execute(
            "SELECT edinet_code FROM filings WHERE session_id = ? LIMIT 1", [session_id]
        ).fetchone()
        assert row is not None
