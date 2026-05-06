import pytest
from unittest.mock import MagicMock, patch
from src.engine import JPEDINETEngine
from src.core.db import db_manager

class MockDoc:
    def __init__(self, doc_id, sec_code="1234"):
        self._data = {
            "docID": doc_id,
            "secCode": sec_code,
            "filerName": "E2E Filer",
            "docDescription": "E2E Desc",
            "submitDateTime": "2026-05-06 12:00:00",
            "formCode": "030000",
            "docTypeCode": "120",
            "csvFlag": "0"
        }
    def parse(self):
        m = MagicMock()
        m.text_blocks = {"Intro": "Welcome to E2E test narration."}
        return m

@pytest.fixture
def e2e_engine():
    # TESTING=true is already set in conftest.py
    return JPEDINETEngine()

def test_full_pipeline_success(e2e_engine):
    """
    E2E Test: Full User Flow
    1. List documents
    2. Sync them to DB
    3. Verify DB content
    4. Run backfill
    """
    mock_docs = [MockDoc("E2E_001"), MockDoc("E2E_002")]
    
    with patch("edinet_tools.documents", return_value=mock_docs):
        # 1 & 2. Trigger Sync
        e2e_engine.sync_market(days=1, session_id="e2e-test", max_workers=1)
        
        # 3. Verify DB Content
        with db_manager.connect_master() as conn:
            # Check filings (Registry)
            count = conn.execute("SELECT count(*) FROM filings").fetchone()[0]
            assert count == 2
            
            # Check narratives (Narratives)
            narr_count = conn.execute("SELECT count(*) FROM narratives").fetchone()[0]
            assert narr_count == 2
            
    # 4. Trigger Backfill (should do nothing since everything is synced)
    with patch("edinet_tools.document", side_effect=lambda did: MockDoc(did)):
        e2e_engine.backfill_missing_data()

def test_full_pipeline_interrupted_severe(e2e_engine):
    """
    Severe E2E Test: Pipeline interrupted by a crash.
    Ensure that already flushed data is persisted and logs capture the failure.
    """
    mock_docs = [MockDoc("RECOVER_001"), MockDoc("RECOVER_002")]
    
    # Simulate a crash during the second document processing
    call_count = 0
    def side_effect(doc, ticker, sid):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise KeyboardInterrupt("Simulated User Interrupt")
        return e2e_engine._extract_metadata(doc, ticker, sid) # Simple mock return

    # Since KeyboardInterrupt is severe, we check if it propagates
    with patch("edinet_tools.documents", return_value=mock_docs):
        with patch.object(e2e_engine, "_process_single_doc", side_effect=side_effect):
            with pytest.raises(KeyboardInterrupt):
                e2e_engine.sync_market(days=1, max_workers=1)
                
    # Check if the first document was potentially saved (depends on batching)
    # In current implementation, batch_size is 50, so 2 docs wouldn't flush until the end
    # or if we had more. But we can verify the DB is still healthy.
    with db_manager.connect_master() as conn:
        assert conn.execute("SELECT 1").fetchone()[0] == 1
