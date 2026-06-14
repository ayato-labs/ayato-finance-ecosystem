from datetime import datetime, timedelta

from src.fetchers.yf_fetcher import YFinanceFetcher


def test_yf_fetcher_real_sp500():
    """S&P 500 (^GSPC) を実際に取得してスキーマ整合性を確認"""
    fetcher = YFinanceFetcher()
    start_date = datetime.now() - timedelta(days=5)
    df = fetcher.fetch("^GSPC", start_date)

    assert not df.empty
    # schema.py で定義されているはずの標準カラムを確認
    assert "Date" in df.columns
    assert "Close" in df.columns
    assert "Ticker" in df.columns
    assert (df["Ticker"] == "^GSPC").all()


def test_yf_fetcher_invalid_ticker():
    """不正なティッカーでの挙動"""
    fetcher = YFinanceFetcher()
    df = fetcher.fetch("INVALID_TICKER_99999", datetime.now())
    assert df.empty
