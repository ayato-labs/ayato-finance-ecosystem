from src.fetchers.crypto_fetcher import CryptoPriceFetcher


def test_fetcher_standardizes_ticker():
    fetcher = CryptoPriceFetcher()
    # No network call here, just testing the logic if we were to call it
    # Actually, the fetcher code converts BTC -> BTC-USD
    # I'll test a real small fetch for BTC-USD to ensure yfinance is working
    df = fetcher.fetch_daily_data("BTC", days=1)
    assert not df.empty
    assert "Date" in df.columns
    assert "Close" in df.columns
    assert len(df) >= 1


def test_fetcher_handles_invalid_ticker():
    fetcher = CryptoPriceFetcher()
    df = fetcher.fetch_daily_data("NON_EXISTENT_COIN_12345", days=1)
    assert df.empty


def test_fetcher_handles_days_parameter():
    fetcher = CryptoPriceFetcher()
    df = fetcher.fetch_daily_data("BTC", days=5)
    # yfinance might return 4-6 days depending on the time, but definitely more than 1
    assert len(df) > 1


def test_fetcher_fetches_metadata_success():
    fetcher = CryptoPriceFetcher()
    # Real network call for BTC
    meta = fetcher.fetch_metadata("BTC")
    assert meta != {}
    assert "circulating_supply" in meta
    assert meta["circulating_supply"] > 0
    assert "description" in meta


def test_fetcher_metadata_invalid_ticker():
    fetcher = CryptoPriceFetcher()
    meta = fetcher.fetch_metadata("NON_EXISTENT_COIN_999")
    # yfinance usually returns empty dict or dict with None values
    # In our fetcher, we catch exception or return empty if info is None
    assert meta == {} or all(v is None for v in meta.values())
