import pytest
import os
import pandas as pd
from edgar_core.storage import EdgarStorage

@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test_edgar.duckdb"
    return str(db_path)

def test_storage_init(temp_db):
    storage = EdgarStorage(db_path=temp_db)
    assert os.path.exists(temp_db)
    # Check tables
    stats = storage.get_stats()
    assert stats["total_filings"] == 0

def test_save_filing(temp_db):
    storage = EdgarStorage(db_path=temp_db)
    metadata = {
        "accessionNumber": "000123-26-456",
        "ticker": "AAPL",
        "cik": "0000320193",
        "form": "10-K",
        "filingDate": "2026-06-15"
    }
    sections = {"business": "Sample business content that is long enough to pass the integrity check." * 10}
    
    storage.save_filing(metadata, sections)
    assert storage.filing_exists("000123-26-456")
    
    filings = storage.get_filings_by_ticker("AAPL")
    assert len(filings) == 1
    assert filings[0][1] == "10-K"

def test_save_facts(temp_db):
    storage = EdgarStorage(db_path=temp_db)
    ticker = "AAPL"
    acc_no = "000123-26-456"
    
    # Mock facts DataFrame
    df = pd.DataFrame([
        {
            "concept": "NetIncome",
            "label": "Net Income",
            "numeric_value": 1000000.0,
            "unit_ref": "USD",
            "fiscal_year": 2026,
            "fiscal_period": "FY",
            "period_start": "2025-10-01",
            "period_end": "2026-09-30",
            "period_instant": None
        }
    ])
    
    storage.save_facts(ticker, acc_no, df)
    assert storage.facts_exist(acc_no)
    
    repair_list = storage.get_accession_numbers_needing_repair()
    # If filing doesn't exist in 'filings' table, it might still show up in repair depending on query
    # But current query is LEFT JOIN where filings has it but facts doesn't.
    # So if we didn't save filing, it won't be in repair list.
    assert len(repair_list) == 0 

def test_repair_logic(temp_db):
    storage = EdgarStorage(db_path=temp_db)
    metadata = {
        "accessionNumber": "999-99-999",
        "ticker": "TSLA",
        "cik": "12345",
        "form": "10-Q",
        "filingDate": "2026-06-15"
    }
    storage.save_filing(metadata, {"risk": "Long enough content for risk factors section" * 10})
    
    # Facts not saved yet
    repair_list = storage.get_accession_numbers_needing_repair()
    assert len(repair_list) == 1
    assert repair_list[0][0] == "999-99-999"
