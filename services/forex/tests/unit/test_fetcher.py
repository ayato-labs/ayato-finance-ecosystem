from datetime import datetime, timedelta

from src.fetchers.forex_fetcher import ForexFetcher


def test_forex_fetcher_usd():
    """USDは常に1.0であることを確認(実API不要)"""
    fetcher = ForexFetcher()
    start_date = datetime(2024, 1, 1)
    df = fetcher.fetch("USD", start_date)
    assert not df.empty
    assert (df["Rate"] == 1.0).all()
    assert (df["Symbol"] == "USD").all()


def test_forex_fetcher_jpy_real():
    """JPYの対ドルレートを実API(yfinance)で取得するテスト"""
    fetcher = ForexFetcher()
    # 直近3日分程度
    start_date = datetime.now() - timedelta(days=3)
    df = fetcher.fetch("JPY", start_date)

    assert not df.empty
    assert "Rate" in df.columns
    assert "Date" in df.columns
    # 1 JPY は 0.005〜0.01 USD 程度の範囲のはず(異常な値でないことの確認)
    latest_rate = df.iloc[-1]["Rate"]
    min_jpy_rate = 0.001
    max_jpy_rate = 0.02
    assert min_jpy_rate < latest_rate < max_jpy_rate


def test_forex_fetcher_eur_real():
    """EURの対ドルレートを実APIで取得するテスト"""
    fetcher = ForexFetcher()
    start_date = datetime.now() - timedelta(days=3)
    df = fetcher.fetch("EUR", start_date)

    assert not df.empty
    # 1 EUR は 1.0 USD 前後
    latest_rate = df.iloc[-1]["Rate"]
    min_eur_rate = 0.5
    max_eur_rate = 2.0
    assert min_eur_rate < latest_rate < max_eur_rate


def test_forex_fetcher_unsupported():
    """サポートされていない通貨での挙動"""
    fetcher = ForexFetcher()
    df = fetcher.fetch("INVALID", datetime.now())
    assert df.empty


def test_forex_fetcher_future_date():
    """未来の日付を指定した場合"""
    fetcher = ForexFetcher()
    start_date = datetime.now() + timedelta(days=365)
    df = fetcher.fetch("JPY", start_date)
    # データは空になるはず
    assert df.empty
