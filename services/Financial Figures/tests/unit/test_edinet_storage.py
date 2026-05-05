def test_save_and_get_document(storage):
    """Test saving and checking document existence."""
    doc_data = {
        "docID": "S100TEST",
        "filerName": "Test Corp",
        "secCode": "80010",
        "docDescription": "有価証券報告書",
        "submitDateTime": "2024-03-29 10:00:00"
    }
    storage.save_document(doc_data)
    
    assert "S100TEST" in storage.get_existing_doc_ids(["S100TEST"])
    assert "NON_EXISTENT" not in storage.get_existing_doc_ids(["NON_EXISTENT"])

def test_save_raw_facts(storage):
    """Test saving raw facts from parsed content."""
    # Must save document first due to FK constraint
    storage.save_document({"docID": "S100TEST", "filerName": "Test"})
    facts = [
        {"id": "Sales", "name": "Net Sales", "context": "curr", "value": 1000.0, "unit": "JPY"},
        {"id": "NetIncome", "name": "Net Income", "context": "curr", "value": 100.0, "unit": "JPY"}
    ]
    storage.save_facts("S100TEST", facts)
    
    retrieved = storage.get_facts_by_doc("S100TEST")
    assert len(retrieved) == 2
    assert retrieved[0]["id"] == "Sales"

def test_get_existing_doc_ids(storage):
    """Test retrieving existing doc IDs in bulk."""
    storage.save_document({"docID": "DOC1", "filerName": "A"})
    storage.save_document({"docID": "DOC2", "filerName": "B"})
    
    existing = storage.get_existing_doc_ids(["DOC1", "DOC2", "DOC3"])
    assert "DOC1" in existing
    assert "DOC2" in existing
    assert "DOC3" not in existing

def test_save_normalized_facts(storage):
    """Test saving normalized facts to the norm database."""
    facts = [
        {
            "DisclosedDate": "2024-03-29",
            "LocalCode": "8001",
            "FiscalYear": "2024",
            "FiscalPeriod": "FY",
            "NetSales": 5000.0,
            "accession_number": "S100TEST",
            "session_id": "session_1"
        }
    ]
    storage.save_normalized_facts(facts)
    
    # Verify existence using doc_ids bulk check
    existing = storage.get_existing_norm_ids(["S100TEST"])
    assert "S100TEST" in existing
