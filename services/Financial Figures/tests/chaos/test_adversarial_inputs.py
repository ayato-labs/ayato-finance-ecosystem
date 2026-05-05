import pytest
import duckdb
from src.core.config import settings
from src.edinet.storage import EDINETStorage
from src.edinet.parser import EDINETParser

def test_parser_resilience_malformed_xml():
    """Test parser with completely broken XML content."""
    parser = EDINETParser()
    broken_xml = "<xbrl><incomplete_tag>data"
    
    # Parser should handle errors gracefully, likely returning empty list or raising specific error
    facts = parser.parse_financial_csv(broken_xml)
    assert facts == [] or isinstance(facts, list)

def test_storage_extreme_values(test_settings):
    """Test storage with extremely large numbers or invalid types."""
    storage = EDINETStorage()
    doc_id = "CHAOS_DOC"
    # Must save document first due to FK constraint
    storage.save_document({"docID": doc_id, "filerName": "ChaosCorp"})
    
    # Injecting a massive number that might exceed standard float/int limits
    extreme_facts = [
        {"id": "Inf", "name": "Infinity", "context": "c", "value": 1e308, "unit": "JPY"}, # Near float max
        {"id": "Large", "name": "Large", "context": "c", "value": 10.0**20, "unit": "JPY"}   # Large float
    ]
    
    # Should not crash the DB
    storage.save_facts(doc_id, extreme_facts)
    retrieved = storage.get_facts_by_doc(doc_id)
    assert len(retrieved) == 2

def test_db_corruption_simulation(test_settings, tmp_path):
    """Test behavior when the DuckDB file is overwritten by garbage."""
    storage = EDINETStorage()
    db_path = settings.DB_PATH_EDINET_RAW
    
    # Initialize and save something
    storage.save_document({"docID": "S1", "filerName": "A"})
    
    # CORRUPT: Overwrite the file with random bytes
    with open(db_path, "wb") as f:
        f.write(b"NOT_A_DB_FILE" * 100)
    
    # Operations should now raise meaningful errors or handle corruption
    with pytest.raises(Exception):
        storage.get_existing_doc_ids(["S1"])
    
    # Verify we can still use other shards if they aren't corrupted (not possible here since we use same storage instance)
    # But we can at least check it doesn't hang forever beyond timeout.
    pass

def test_sql_injection_attempt(storage):
    """Test resilience against SQL injection in doc IDs."""
    malicious_id = "S1'; DROP TABLE company_facts; --"
    
    # Should be handled safely via placeholders
    storage.get_existing_doc_ids([malicious_id])
    # Check if table still exists
    storage.save_document({"docID": "SAFE", "filerName": "Test"})
    assert "SAFE" in storage.get_existing_doc_ids(["SAFE"])
