import pytest
import os
import json
from pathlib import Path
from src.storage import FinancialNarrativeStorage

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_narratives.duckdb"
    return str(db_file)

def test_storage_init(temp_db):
    storage = FinancialNarrativeStorage(db_path=temp_db)
    assert Path(temp_db).exists()
    # Check tables
    import duckdb
    with duckdb.connect(temp_db) as conn:
        tables = conn.execute("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]
        assert "filings" in table_names
        assert "structured_data" in table_names

def test_save_and_get_filing(temp_db):
    storage = FinancialNarrativeStorage(db_path=temp_db)
    metadata = {
        "accessionNumber": "000-111-222",
        "ticker": "TEST",
        "cik": "1234567890",
        "form": "10-K",
        "filingDate": "2026-01-01"
    }
    sections = {"business": "Testing business section content."}
    
    storage.save_filing(metadata, sections)
    
    # Retrieve
    filings = storage.get_filings_by_ticker("TEST")
    assert len(filings) == 1
    assert filings[0][0] == "TEST"
    assert filings[0][1] == "10-K"
    assert json.loads(filings[0][3]) == sections

def test_save_and_get_structuring(temp_db):
    storage = FinancialNarrativeStorage(db_path=temp_db)
    acc_no = "000-111-222"
    ticker = "TEST"
    facts = {
        "capex": {"intent": "new factory", "amount": 1000},
        "rd": {"focus": "AI"},
        "governance": None
    }
    
    storage.save_structuring(acc_no, ticker, facts)
    
    # Retrieve
    retrieved = storage.get_structuring_by_ticker("TEST")
    assert retrieved == facts

def test_filing_exists(temp_db):
    storage = FinancialNarrativeStorage(db_path=temp_db)
    acc_no = "999-888"
    assert not storage.filing_exists(acc_no)
    
    metadata = {
        "accessionNumber": acc_no,
        "ticker": "EXIST",
        "form": "10-Q",
        "filingDate": "2026-02-01"
    }
    storage.save_filing(metadata, {"content": "data"})
    assert storage.filing_exists(acc_no)

def test_save_filing_true_upsert(temp_db):
    """
    【DBエンジニア視点のテスト】
    INSERT OR REPLACE が真に機能しているか、重複行を生まずに安全に更新できるかを証明する。
    """
    storage = FinancialNarrativeStorage(db_path=temp_db)
    acc_no = "UPSERT-001"
    ticker = "TEST"
    
    # 1回目の保存
    metadata_v1 = {"accessionNumber": acc_no, "ticker": ticker, "form": "10-K", "filingDate": "2026-01-01"}
    sections_v1 = {"business": "Old Business Text"}
    storage.save_filing(metadata_v1, sections_v1)
    
    # 2回目の保存 (同じ accessionNumber で内容を更新)
    metadata_v2 = {"accessionNumber": acc_no, "ticker": ticker, "form": "10-K/A", "filingDate": "2026-01-02"}
    sections_v2 = {"business": "New Business Text", "risk": "New Risk Text"}
    storage.save_filing(metadata_v2, sections_v2)
    
    # 検証
    filings = storage.get_filings_by_ticker(ticker)
    
    # 1. 重複行が作られていないこと (1件のまま)
    assert len(filings) == 1, "UPSERTが機能しておらず、重複レコードが生成されています。"
    
    # 2. 内容がV2で上書きされていること
    assert filings[0][1] == "10-K/A" # Form
    assert json.loads(filings[0][3]) == sections_v2 # Sections
    
def test_save_filing_invalid_metadata(temp_db):
    storage = FinancialNarrativeStorage(db_path=temp_db)
    # accessionNumber is missing
    with pytest.raises(ValueError, match="Missing required metadata fields"):
        storage.save_filing({"ticker": "MISSING"}, {"content": "fail"})

def test_special_characters_handling(temp_db):
    """あえて厳しいテスト: 特殊文字や巨大なJSONの保存"""
    storage = FinancialNarrativeStorage(db_path=temp_db)
    metadata = {
        "accessionNumber": "SPECIAL-123",
        "ticker": "SPEC",
        "form": "10-K",
        "filingDate": "2026-01-01"
    }
    # 絵文字、SQLインジェクション風の文字列、巨大なテキスト
    sections = {
        "weird_chars": "🚀 ' OR 1=1; -- \n\t\r \"",
        "huge_content": "A" * (1024 * 1024)  # 1MB
    }
    
    storage.save_filing(metadata, sections)
    
    filings = storage.get_filings_by_ticker("SPEC")
    retrieved_sections = json.loads(filings[0][3])
    assert retrieved_sections["weird_chars"] == sections["weird_chars"]
    assert len(retrieved_sections["huge_content"]) == 1024 * 1024
