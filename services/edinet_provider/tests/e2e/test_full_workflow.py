import datetime
from unittest.mock import MagicMock, patch

from src.datalake.engine import JPEDINETEngine
from src.datalake.shared.infra.db import db_manager


class MockDoc:
    def __init__(self, doc_id, date):
        self._data = {
            "docID": doc_id,
            "submitDateTime": f"{date} 10:00",
            "formCode": "030000",
            "csvFlag": "0",
        }

    def parse(self):
        m = MagicMock()
        m.text_blocks = {
            "Key": "This is a sufficiently long narrative block for the E2E test to pass."
        }
        return m


def test_full_user_workflow_sync(tmp_path, monkeypatch):
    """
    E2E: Simulate a user running a market sync for 2 days.
    Checks list fetching, parallel processing, and DB persistence.
    """
    monkeypatch.setenv("MASTER_DB_PATH", str(tmp_path / "e2e_master.db"))
    monkeypatch.setenv("REGISTRY_DB_PATH", str(tmp_path / "e2e_reg.db"))
    monkeypatch.setenv("FACTS_DB_PATH", str(tmp_path / "e2e_facts.db"))
    monkeypatch.setenv("NARRATIVE_DB_PATH", str(tmp_path / "e2e_narr.db"))

    engine = JPEDINETEngine()

    # Mock dates
    today = datetime.date(2024, 5, 7)

    # Mocking DataRepository.get_documents_with_cache to return document objects
    docs_today = [MockDoc("E2E_001", "2024-05-07")]
    docs_yesterday = [MockDoc("E2E_002", "2024-05-06")]

    with patch(
        "src.datalake.shared.queries.repository.DataRepository.get_documents_with_cache"
    ) as mock_fetch:
        mock_fetch.side_effect = lambda d: docs_today if d == today else docs_yesterday

        # Run sync
        engine.sync_market(days=2, end_date=today, max_workers=2)

    # VERIFY DB across all shards
    with db_manager.connect_master(read_only=True) as conn:
        # Check registry
        ids = {row[0] for row in conn.execute("SELECT doc_id FROM registry_db.filings").fetchall()}
        assert "E2E_001" in ids
        assert "E2E_002" in ids

        # Check narratives
        narrs = conn.execute("SELECT count(*) FROM narr_db.narratives").fetchone()[0]
        assert narrs >= 2

        # Check ingestion log
        logs = conn.execute("SELECT status FROM ingestion_log").fetchall()
        assert len(logs) == 2
        assert all(log_entry[0] == "SUCCESS" for log_entry in logs)
