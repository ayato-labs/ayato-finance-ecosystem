import pytest
import pandas as pd
from edgar_core.storage import EdgarStorage, DataIntegrityError

@pytest.fixture
def storage(tmp_path):
    db_path = tmp_path / "chaos_test.duckdb"
    return EdgarStorage(db_path=str(db_path))

def test_chaos_truncated_sections(storage):
    """HTMLパース結果が極端に短い（破損・タイムアウト疑い）場合に拒否されるか検証"""
    metadata = {
        "accessionNumber": "000-00-001",
        "ticker": "AAPL",
        "form": "10-K",
        "filingDate": "2026-06-15"
    }
    # 100文字未満のコンテンツ（ADR-0005の閾値）
    sparse_sections = {"business": "Too short content"}
    
    with pytest.raises(DataIntegrityError) as excinfo:
        storage.save_filing(metadata, sparse_sections)
    
    assert "too sparse" in str(excinfo.value)
    assert not storage.filing_exists("000-00-001")

def test_chaos_empty_facts(storage):
    """財務データ（XBRL）が空の場合に拒否されるか検証"""
    with pytest.raises(DataIntegrityError) as excinfo:
        storage.save_facts("AAPL", "000-00-001", pd.DataFrame())
    
    assert "Facts DataFrame is empty" in str(excinfo.value)
    assert not storage.facts_exist("000-00-001")

def test_chaos_missing_metadata(storage):
    """メタデータが欠損している場合に拒否されるか検証"""
    incomplete_metadata = {
        "accessionNumber": "000-00-001",
        # ticker missing
        "form": "10-K"
    }
    sections = {"business": "A" * 200}
    
    with pytest.raises(DataIntegrityError) as excinfo:
        storage.save_filing(incomplete_metadata, sections)
    
    assert "Missing metadata fields" in str(excinfo.value)

def test_chaos_missing_columns_in_facts(storage):
    """財務データのカラムが不足している場合に拒否されるか検証"""
    bad_df = pd.DataFrame([{"wrong_col": 123}])
    
    with pytest.raises(DataIntegrityError) as excinfo:
        storage.save_facts("AAPL", "000-00-001", bad_df)
    
    assert "Missing columns" in str(excinfo.value)
