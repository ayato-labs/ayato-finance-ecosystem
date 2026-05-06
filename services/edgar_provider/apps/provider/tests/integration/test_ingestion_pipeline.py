from unittest.mock import MagicMock, patch

import pytest
from edgar_core.config import settings
from edgar_core.db import db_manager
from edgar_provider.engine import USEngine


def test_ticker_ingestion_pipeline_integration(tmp_path, monkeypatch):
    """
    Integration Test: Verify the 'Ticker Sync' feature.
    Connects fetching logic, parsing, and saving.
    Mocks allowed for external SEC API.
    """
    test_db = tmp_path / "integration_ingest.duckdb"
    monkeypatch.setattr(settings, "FACTS_DB_PATH", test_db)
    monkeypatch.setattr(settings, "NARRATIVES_DB_PATH", test_db) # Combined for test
    
    engine = USEngine()
    
    # Mock 'edgar.Company' and its methods
    with patch("edgar_provider.engine.Company") as MockCompany:
        mock_company_inst = MockCompany.return_value
        mock_company_inst.cik = "0000320193"
        mock_company_inst.ticker = "AAPL"
        
        # Mock filings
        mock_filing = MagicMock()
        mock_filing.form = "10-K"
        mock_filing.filed_date = "2024-01-01"
        mock_filing.accession_number = "TEST-ACCN-999"
        # Mock narrative content
        mock_filing.markdown.return_value = "## Item 1A. Risk Factors\nExtreme heat is a risk."
        
        mock_company_inst.get_filings.return_value = [mock_filing]
        
        # Mock facts
        mock_company_inst.get_facts.return_value.to_dict.return_value = {
            "facts": {
                "us-gaap": {
                    "Revenue": {
                        "label": "Revenue",
                        "units": {"USD": [{"val": 5000, "accn": "TEST-ACCN-999", "fy": 2023, "fp": "FY", "form": "10-K", "filed": "2024-01-01"}]}
                    }
                }
            }
        }
        
        # Execute Feature: Fetch and Ingest
        engine.fetch_and_ingest_company("AAPL", "session-int-123", limit=1)
        
        # Verify result in DB
        with db_manager.connect(test_db) as conn:
            res = conn.execute("SELECT label, value FROM company_facts WHERE accession_number = 'TEST-ACCN-999'").fetchone()
            assert res[0] == "Revenue"
            assert res[1] == 5000.0
            
            nar = conn.execute("SELECT section_name FROM narratives WHERE ticker = 'AAPL'").fetchone()
            assert nar[0] == "Risk Factors"
