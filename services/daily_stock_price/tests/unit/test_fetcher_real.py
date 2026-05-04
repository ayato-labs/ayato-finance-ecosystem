from datetime import datetime, timedelta

from src.fetchers.yf_fetcher import YFinanceFetcher


def test_yf_fetcher_real_aapl():
    """AAPLを実際に取得してスキーマ整合性を確認"""
    fetcher = YFinanceFetcher()
    start_date = datetime.now() - timedelta(days=5)
    df = fetcher.fetch("AAPL", start_date)

    assert not df.empty
    assert "Date" in df.columns
    assert "Close" in df.columns
    assert "Ticker" in df.columns
    assert (df["Ticker"] == "AAPL").all()
    # 分割データが含まれているか (actions=True)
    assert "StockSplits" in df.columns


def test_yf_fetcher_real_batch():
    """複数銘柄のバッチ取得を実際に検証"""
    fetcher = YFinanceFetcher()
    start_date = datetime.now() - timedelta(days=5)
    tickers = ["AAPL", "MSFT"]
    df = fetcher.fetch_batch(tickers, start_date)

    assert not df.empty
    unique_tickers = df["Ticker"].unique()
    assert "AAPL" in unique_tickers
    assert "MSFT" in unique_tickers
