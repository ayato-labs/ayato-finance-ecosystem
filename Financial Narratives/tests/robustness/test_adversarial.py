import pytest
import requests
from src.edgar_parser import EdgarParser
from src.storage import FinancialNarrativeStorage
from src.edgar_fetcher import EdgarFetcher

def test_parser_with_corrupted_html():
    parser = EdgarParser()
    corrupted_html = "<html><body> Item 1. Business <p>Some content... [MISSING END]"
    sections = parser.extract_all_sections(corrupted_html, "10-K")
    assert isinstance(sections, dict)

def test_storage_invalid_metadata(temp_db_path):
    """必須キーが欠損したメタデータでの保存試行 (Primary KeyがNoneになる場合)"""
    storage = FinancialNarrativeStorage(temp_db_path)
    # 必須キー 'accessionNumber' がない辞書を渡す
    with pytest.raises(Exception):
        storage.save_filing({"ticker": "AAPL"}, {"mda": "test"})

def test_fetcher_network_error(mocker):
    """SECサーバーが500エラーを返した場合"""
    fetcher = EdgarFetcher("TestAgent")
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.status_code = 500
    
    # get_latest_submissionsがNoneを返し、クラッシュしないことを確認
    subs = fetcher.get_latest_submissions("AAPL")
    assert subs is None

def test_fetcher_with_invalid_ticker():
    fetcher = EdgarFetcher("TestAgent")
    cik = fetcher.get_cik("INVALID_TICKER_99999")
    assert cik is None
