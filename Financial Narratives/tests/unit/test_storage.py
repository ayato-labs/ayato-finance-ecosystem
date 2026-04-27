import pytest
from src.storage import FinancialNarrativeStorage

def test_storage_init_and_save(temp_db_path, mock_filing_metadata):
    storage = FinancialNarrativeStorage(temp_db_path)
    sections = {"mda": "test content"}
    
    storage.save_filing(mock_filing_metadata, sections)
    
    # 存在確認のテスト
    assert storage.filing_exists(mock_filing_metadata["accessionNumber"]) is True
    assert storage.filing_exists("NON-EXISTENT") is False
    
    # サマリーの確認
    summary = storage.get_summary()
    assert len(summary) == 1
    assert summary[0][0] == "TEST"

def test_storage_upsert(temp_db_path, mock_filing_metadata):
    storage = FinancialNarrativeStorage(temp_db_path)
    
    # 1回目
    storage.save_filing(mock_filing_metadata, {"mda": "version 1"})
    # 2回目 (上書き)
    storage.save_filing(mock_filing_metadata, {"mda": "version 2"})
    
    # 重複せずに1レコードのみ存在することを確認
    summary = storage.get_summary()
    assert len(summary) == 1
