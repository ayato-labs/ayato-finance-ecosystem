from unittest.mock import MagicMock
import pytest
from src.engine import JPEDINETEngine
from src.core.db import db_manager

def test_engine_flush_results_to_db(engine):
    """
    Integration Test: Verify that the engine correctly flushes results into the Quad-Split DB.
    Mocks are allowed here to simulate processing results.
    """
    sample_results = [
        {
            "metadata": ["DOC001", "E001", "7203", "Toyota", "Annual", "2026-05-01", "030000", "120", "session-1"],
            "narratives": [["DOC001", "BusinessRisks", "Risks are high"]],
            "facts": [["DOC001", "Sales", 100.0, "JPY", "csv1", 2026, "FY"]]
        }
    ]
    
    with db_manager.connect_master() as conn:
        # Clear if exists (though it's session engine/in-memory)
        conn.execute("DELETE FROM filings WHERE doc_id = 'DOC001'")
        
        # Flush
        engine._flush_results_to_db(conn, sample_results)
        
        # Verify
        res = conn.execute("SELECT filer_name FROM filings WHERE doc_id = 'DOC001'").fetchone()
        assert res[0] == "Toyota"
        
        # Verify narratives
        narr = conn.execute("SELECT content_md FROM narratives WHERE doc_id = 'DOC001'").fetchone()
        assert narr[0] == "Risks are high"
        
        # Verify facts
        fact = conn.execute("SELECT item_value FROM company_facts WHERE doc_id = 'DOC001'").fetchone()
        assert fact[0] == 100.0
