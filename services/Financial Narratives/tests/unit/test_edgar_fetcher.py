
from src.edgar_fetcher import EdgarFetcher

USER_AGENT = "SampleAgent test@example.com"


def test_edgar_fetcher_init():
    fetcher = EdgarFetcher(USER_AGENT)
    assert fetcher.headers["User-Agent"] == USER_AGENT


def test_edgar_fetcher_get_cik_real():
    """SEC ticker listを実際に取得してマッピングを確認"""
    fetcher = EdgarFetcher(USER_AGENT)
    cik = fetcher.get_cik("AAPL")
    assert cik == "0000320193"


def test_edgar_fetcher_get_latest_submissions_real():
    """SEC APIを実際に叩いて提出書類リストを取得"""
    fetcher = EdgarFetcher(USER_AGENT)
    subs = fetcher.get_latest_submissions("AAPL")
    assert subs is not None
    assert "cik" in subs
    # API might return integer as string, or normalized string.
    # Based on failure, it returns '0000320193'
    assert subs["cik"].lstrip("0") == "320193"


def test_edgar_fetcher_filter_relevant_filings():
    fetcher = EdgarFetcher(USER_AGENT)
    dummy_subs = {
        "filings": {
            "recent": {
                "form": ["10-K", "8-K", "10-Q"],
                "accessionNumber": ["1", "2", "3"],
                "filingDate": ["D1", "D2", "D3"],
                "primaryDocument": ["P1", "P2", "P3"],
                "primaryDocDescription": ["DESC1", "DESC2", "DESC3"],
            }
        }
    }
    relevant = fetcher.filter_relevant_filings(dummy_subs, ["10-K"])
    assert len(relevant) == 1
    assert relevant[0]["form"] == "10-K"


def test_edgar_fetcher_invalid_ticker():
    """存在しないティッカーでエラーを誘発"""
    fetcher = EdgarFetcher(USER_AGENT)
    cik = fetcher.get_cik("INVALID_TICKER_X")
    assert cik is None

    subs = fetcher.get_latest_submissions("INVALID_TICKER_X")
    assert subs is None
