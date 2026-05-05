import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from src.engine import JPEDINETEngine
from src.core.db import db_manager

def test_sync_to_storage_flow(engine, mocker):
    """
    E2E Test: A complete user flow from API fetch to multi-tier DB storage.
    Simulation of historical sync for one company.
    """
    # 1. Mock API and Document behavior
    mock_doc = MagicMock()
    mock_doc._data = {
        "docID": "E2E_DOC_001",
        "edinetCode": "E999",
        "secCode": "9999",
        "filerName": "E2E Test Corp",
        "docDescription": "E2E Annual Report",
        "submitDateTime": "2026-05-01 12:00:00",
        "formCode": "030000",
        "docTypeCode": "120",
        "csvFlag": "1"
    }
    
    # Mock parse results
    mock_report = MagicMock()
    mock_report.text_blocks = {"BusinessRisks": "Our business is testing."}
    mock_doc.parse.return_value = mock_report
    
    # Mock network call for CSV (in engine._extract_facts)
    mocker.patch("src.core.csv_parser.get_csv_from_edinet", return_value=b"zip_content")
    # Mock CSV parsing to return a dummy DF
    mocker.patch("src.core.csv_parser.parse_edinet_csv", return_value={
        "e2e_facts.csv": pd.DataFrame({
            "item": [None, "Sales", None, None, None, None, None, "JPY", "5000"],
        }).T # Simplistic mock of the row structure expected by engine
    })
    
    # Fix the mock DataFrame to match the engine's column expectations (cols[1], cols[7], cols[8])
    # item_name = row[cols[1]], unit = row[cols[7]], item_value = row[cols[8]]
    df = pd.DataFrame(columns=[f"col{i}" for i in range(10)])
    df.loc[0] = ["x", "Sales", "x", "x", "x", "x", "x", "JPY", "5000", "x"]
    mocker.patch("src.core.csv_parser.parse_edinet_csv", return_value={"test.csv": df})
    
    # Mock edinet_tools.entity
    mock_entity = mocker.patch("edinet_tools.entity")
    mock_entity.return_value.documents.return_value = [mock_doc]

    # 2. Execute Sync
    engine.sync_company("9999", days=1)

    # 3. Verify results in DB
    with db_manager.connect_master() as conn:
        res = conn.execute("SELECT filer_name FROM filings WHERE doc_id = 'E2E_DOC_001'").fetchone()
        assert res[0] == "E2E Test Corp"
        
        narr = conn.execute("SELECT count(*) FROM narratives WHERE doc_id = 'E2E_DOC_001'").fetchone()[0]
        assert narr == 1
        
        facts = conn.execute("SELECT item_value FROM company_facts WHERE doc_id = 'E2E_DOC_001'").fetchone()[0]
        assert facts == 5000.0
import pandas as pd
