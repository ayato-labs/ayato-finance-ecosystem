from unittest.mock import patch
from src.core.db import db_manager


class MockDoc:
    def __init__(self, doc_id, edinet_code="E12345", sec_code="0000"):
        self._data = {
            "docID": doc_id,
            "edinetCode": edinet_code,
            "secCode": sec_code,
            "filerName": "E2E Filer",
            "docDescription": "E2E Desc",
            "submitDateTime": "2024-05-01 10:00:00",
            "formCode": "030000",
            "docTypeCode": "120",
            "csvFlag": "0",
        }

    def parse(self):
        return None


def test_full_pipeline_success(engine):
    """
    E2E Test: Full User Flow
    """
    mock_docs = [MockDoc("E2E_001"), MockDoc("E2E_002")]

    with patch("edinet_tools.documents", return_value=mock_docs):
        # 1 & 2. Trigger Sync
        engine.sync_market(days=1, session_id="e2e-test", max_workers=1)

        # 3. Verify DB Content
        with db_manager.connect_master() as conn:
            # Check filings (Registry)
            count = conn.execute("SELECT count(*) FROM registry_db.filings").fetchone()[0]
            assert count >= 2

            # Check a specific record
            res = conn.execute(
                "SELECT filer_name FROM registry_db.filings WHERE doc_id='E2E_001'"
            ).fetchone()
            assert res[0] == "E2E Filer"


def test_backfill_logic(engine):
    """
    E2E Test: Backfill logic identification
    """
    # Create some dummy filings without narratives/facts
    with db_manager.connect_master() as conn:
        conn.execute(
            "INSERT INTO registry_db.filings (doc_id, form_code, session_id) VALUES ('E2E_BACKFILL_1', '030000', 'test')"
        )

    with db_manager.connect_master() as conn:
        query = "SELECT count(*) FROM registry_db.filings WHERE doc_id = 'E2E_BACKFILL_1'"
        count = conn.execute(query).fetchone()[0]
        assert count == 1

        # Verify they don't have narratives yet
        nav_count = conn.execute(
            "SELECT count(*) FROM narr_db.narratives WHERE doc_id = 'E2E_BACKFILL_1'"
        ).fetchone()[0]
        assert nav_count == 0
