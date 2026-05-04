import os
import pytest
from datetime import date
from src.edgar_fetcher import EdgarFetcher
from src.edinet_fetcher import EdinetFetcher
from src.config import USER_AGENT

@pytest.mark.skipif(not os.getenv("EDINET_API_KEY"), reason="EDINET_API_KEY not set")
def test_edinet_fetcher_real_list():
    fetcher = EdinetFetcher()
    # 2026-05-01 is a Friday, likely has filings
    res = fetcher.list_documents(date(2026, 5, 1))
    assert isinstance(res, list)
    if res:
        assert "docID" in res[0]

def test_edgar_fetcher_real_ticker_map():
    # USER_AGENT is usually required by SEC
    fetcher = EdgarFetcher(user_agent=USER_AGENT)
    cik = fetcher.get_cik("AAPL")
    assert cik == "0000320193"

@pytest.mark.skipif(not os.getenv("EDINET_API_KEY"), reason="EDINET_API_KEY not set")
def test_edinet_fetcher_invalid_api_key():
    """あえてエラーを引き起こすテスト"""
    fetcher = EdinetFetcher(api_key="INVALID_KEY_999")
    # API key is invalid, should likely return empty list or log error
    res = fetcher.list_documents(date(2026, 5, 1))
    assert res == []

def test_edgar_fetcher_non_existent_ticker():
    fetcher = EdgarFetcher(user_agent=USER_AGENT)
    cik = fetcher.get_cik("NONEXISTENT_TICKER_12345")
    assert cik is None
