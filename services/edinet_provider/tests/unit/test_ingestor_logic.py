from src.datalake.service.ingestor import DataIngestor


class MockDoc:
    def __init__(self, data):
        self._data = data

    def parse(self):
        return None


def test_extract_metadata_logic():
    """
    Unit: Test metadata extraction logic.
    """
    ingestor = DataIngestor()
    mock_doc = MockDoc(
        {
            "docID": "D001",
            "edinetCode": "E001",
            "filerName": "Test Corp",
            "docDescription": "Annual Report",
            "submitDateTime": "2024-05-07 10:00",
            "formCode": "030000",
            "docTypeCode": "120",
        }
    )

    meta = ingestor._extract_metadata(mock_doc, "7203", "session-123")
    assert meta["doc_id"] == "D001"
    assert meta["sec_code"] == "7203"
    assert meta["session_id"] == "session-123"


def test_extract_facts_no_csv_flag():
    """
    Unit: Ensure facts are not extracted if csvFlag is not '1'.
    """
    ingestor = DataIngestor()
    mock_doc = MockDoc({"docID": "D002", "csvFlag": "0"})

    facts = ingestor._extract_facts(mock_doc, "0000", "sess")
    assert facts == []
