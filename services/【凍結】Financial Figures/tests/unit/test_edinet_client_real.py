import pytest
from datetime import date
from src.providers.edinet.client import EDINETClient

@pytest.mark.skip(reason="Avoid hitting EDINET too frequently in basic runs")
def test_edinet_client_real_metadata():
    """Test real EDINET API call to fetch document list for a specific date."""
    client = EDINETClient()
    # Use a fixed date known to have data
    test_date = date(2024, 3, 29)
    
    docs = client.get_document_list(test_date)
    assert isinstance(docs, list)
    if len(docs) > 0:
        assert "docID" in docs[0]
        assert "filerName" in docs[0]

def test_edinet_client_invalid_date_range():
    """Test client behavior with out-of-range dates."""
    client = EDINETClient()
    future_date = date(2099, 1, 1)
    
    # Depending on EDINET behavior, it might return empty list or error
    docs = client.get_document_list(future_date)
    assert docs == []
