import pytest
from unittest.mock import MagicMock, patch
from src.engine import JPEDINETEngine
from src.core.db import db_manager

class MockDoc:
    def __init__(self, doc_id, sec_code="1234"):
        self._data = {
            "docID": doc_id,
            "secCode": sec_code,
            "filerName": "Test Filer",
            "docDescription": "Test Desc",
            "submitDateTime": "2026-05-06 10:00:00",
            "formCode": "030000",
            "docTypeCode": "120",
            "csvFlag": "0"
        }
    def parse(self):
        mock_report = MagicMock()
        mock_report.text_blocks = {"Section1": "This is a long enough text block for testing."}
        return mock_report

@pytest.fixture
def engine():
    # Use in-memory DB for integration testing
    with patch("src.core.config.settings.MASTER_DB_PATH", ":memory:"):
        # Ensure fresh start
        return JPEDINETEngine()

def test_engine_process_single_doc_flow(engine):
    """Integration Test: Verify metadata and narrative extraction flow."""
    doc = MockDoc("DOC001")
    result = engine._process_single_doc(doc, "1234", "test-session")
    
    assert result is not None
    assert result["metadata"]["doc_id"] == "DOC001"
    assert len(result["narratives"]) == 1
    assert result["narratives"][0]["section_name"] == "Section1"

def test_engine_db_flush_severe_error(engine):
    """
    Severe Test: Handle database failure during flush.
    Simulate a connection error or unique constraint violation that shouldn't be silent.
    """
    results = [{
        "metadata": {
            "doc_id": "ERR001", "edinet_code": "E1", "sec_code": "1",
            "filer_name": "N", "doc_description": "D", "submit_datetime": "2026",
            "form_code": "F", "doc_type_code": "T", "session_id": "S"
        },
        "narratives": [],
        "facts": []
    }]
    
    # Mock connection to raise an exception
    with patch("src.core.db.db_manager.connect_master") as mock_conn:
        mock_conn.return_value.__enter__.side_effect = Exception("DB Connection Lost")
        
        with pytest.raises(Exception, match="DB Connection Lost"):
            # We use a real conn object in _flush_results_to_db, but we can mock its methods
            engine._flush_results_to_db(MagicMock(), results)

def test_engine_sync_market_empty(engine):
    """Integration Test: Verify flow when no documents are found."""
    with patch("edinet_tools.documents", return_value=[]):
        # Should finish without error
        engine.sync_market(days=1)

def test_engine_concurrent_processing_partial_failure(engine):
    """
    Severe Test: One document fails, but others should continue or be logged.
    """
    docs = [MockDoc("GOOD"), MockDoc("BAD")]
    
    def side_effect(doc, ticker, sid):
        if doc._data["docID"] == "BAD":
            raise RuntimeError("Extraction failed")
        return {"metadata": {"doc_id": "GOOD", "edinet_code": "E", "sec_code": "S", 
                            "filer_name": "N", "doc_description": "D", "submit_datetime": "T",
                            "form_code": "F", "doc_type_code": "T", "session_id": "S"},
                "narratives": [], "facts": []}

    with patch.object(JPEDINETEngine, "_process_single_doc", side_effect=side_effect):
        with patch.object(JPEDINETEngine, "_flush_results_to_db") as mock_flush:
            engine._process_docs_concurrently(docs, "session", max_workers=2)
            # Should have called flush for the good one
            assert mock_flush.call_count >= 1
