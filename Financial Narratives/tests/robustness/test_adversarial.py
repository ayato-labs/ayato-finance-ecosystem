import pytest
import duckdb
from src.edgar_parser import EdgarParser
from src.storage import FinancialNarrativeStorage
from src.edgar_fetcher import EdgarFetcher

def test_parser_with_corrupted_html():
    """完全に壊れた、あるいは不完全なHTMLでのパース"""
    parser = EdgarParser()
    # 終了タグがなかったり、Itemタグが不自然な位置にあるHTML
    corrupted_html = "<html><body> Item 1. Business <p>Some content... [MISSING END]"
    sections = parser.extract_all_sections(corrupted_html, "10-K")
    
    # クラッシュせずに、辞書（空かもしれないが）を返すことを確認
    assert isinstance(sections, dict)

def test_storage_with_locked_db(temp_db_path, mock_filing_metadata):
    """DBが別のプロセスによってロックされている場合の挙動"""
    # 別のコネクションでDBを専有する
    conn_lock = duckdb.connect(temp_db_path)
    conn_lock.execute("CREATE TABLE lock_test(id INT)")
    
    storage = FinancialNarrativeStorage(temp_db_path)
    
    # DuckDBは単一プロセス書き込みのため、別のコネクションが開いているとエラーになるはず
    # (FinancialNarrativeStorageが内部で新しいコネクションを張ろうとした時に失敗することを期待)
    with pytest.raises(Exception):
        storage.save_filing(mock_filing_metadata, {"mda": "test"})
    
    conn_lock.close()

def test_fetcher_with_invalid_ticker():
    """存在しないティッカーの指定"""
    fetcher = EdgarFetcher("TestAgent")
    # CIKが見つからない場合にNoneを返すことを確認
    cik = fetcher.get_cik("INVALID_TICKER_99999")
    assert cik is None
