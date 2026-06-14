from unittest.mock import patch

from src.datalake.engine import JPEDINETEngine
from src.datalake.shared.infra.db import db_manager
from src.datalake.service.ingestor import DataIngestor


class MockDoc:
    def __init__(self, doc_id, edinet_code="E12345", sec_code="0000"):
        self._data = {
            "docID": doc_id,
            "edinetCode": edinet_code,
            "secCode": sec_code,
            "filerName": "Test Filer",
            "docDescription": "Test Desc",
            "submitDateTime": "2024-01-01 10:00:00",
            "formCode": "030000",
            "docTypeCode": "120",
            "csvFlag": "0",
        }

    def parse(self):
        return None


def test_engine_init_and_sync_skips_existing(tmp_path, monkeypatch):
    """
    Integration: Verify engine skips docs already in filings table.
    """
    monkeypatch.setenv("MASTER_DB_PATH", str(tmp_path / "master.db"))
    monkeypatch.setenv("REGISTRY_DB_PATH", str(tmp_path / "registry.db"))
    monkeypatch.setenv("FACTS_DB_PATH", str(tmp_path / "facts.db"))
    monkeypatch.setenv("NARRATIVE_DB_PATH", str(tmp_path / "narrative.db"))

    engine = JPEDINETEngine()

    mock_doc = MockDoc("DOC001")

    # 1. First sync - should insert
    with patch("edinet_tools.documents", return_value=[mock_doc]):
        engine.sync_market(days=1)

    # Verify insertion
    with db_manager.connect_master(read_only=True) as conn:
        count = conn.execute(
            "SELECT count(*) FROM registry_db.filings WHERE doc_id='DOC001'"
        ).fetchone()[0]
        assert count == 1

    # 2. Second sync - should skip (mocked process_single_doc to check call)
    with patch("edinet_tools.documents", return_value=[mock_doc]):
        with patch.object(DataIngestor, "_process_single_doc") as mock_process:
            engine.sync_market(days=1)
            assert mock_process.call_count == 0
