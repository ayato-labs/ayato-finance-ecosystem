from unittest.mock import MagicMock, patch

import pytest
from edgar_api.server import app
from edgar_core.config import settings
from edgar_core.db import db_manager
from edgar_provider.engine import USEngine
from fastapi.testclient import TestClient

client = TestClient(app)

def test_full_system_flow_ingest_to_query(tmp_path, monkeypatch):
    """
    System Test: Verifies the entire flow from data ingestion to API consumption.
    1. Provider syncs a ticker (mocked network).
    2. API server responds with the ingested data.
    """
    test_db = tmp_path / "system_flow.duckdb"
    # Unified DB path for test simplicity
    monkeypatch.setattr(settings, "DB_PATH", test_db)
    monkeypatch.setattr(settings, "FACTS_DB_PATH", test_db)
    monkeypatch.setattr(settings, "NARRATIVES_DB_PATH", test_db)
    
    engine = USEngine()
    
    # --- Step 1: Ingestion ---
    with patch("edgar_provider.engine.Company") as MockCompany:
        mock_comp = MockCompany.return_value
        mock_comp.cik = "0000001234"
        mock_comp.ticker = "FLOW"
        
        mock_filing = MagicMock()
        mock_filing.accession_number = "FLOW-ACCN"
        mock_filing.form = "10-K"
        mock_filing.filed_date = "2026-01-01"
        mock_filing.markdown.return_value = "## Item 1. Business\nFlowing content."
        mock_comp.get_filings.return_value = [mock_filing]
        
        mock_comp.get_facts.return_value.to_dict.return_value = {
            "facts": {"us-gaap": {"NetIncome": {"label": "Net Income", "units": {"USD": [{"val": 123.0, "accn": "FLOW-ACCN", "fy": 2025, "fp": "FY"}]}}}}
        }
        
        engine.fetch_and_ingest_company("FLOW", "session-flow-1", limit=1)

    # --- Step 2: API Consumption ---
    # Fetch financials
    response = client.get("/financials/FLOW")
    assert response.status_code == 200
    data = response.json()
    assert data[0]["label"] == "Net Income"
    assert data[0]["value"] == 123.0

    # Fetch narratives
    response = client.get("/narratives/FLOW")
    assert response.status_code == 200
    narratives = response.json()
    assert "Flowing content" in narratives[0]["content"]
    assert narratives[0]["section_name"] == "Business"
