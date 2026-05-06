from src.fetchers.crypto_fetcher import CryptoPriceFetcher


def test_crypto_fetcher_real_btc():
    """BTC-USDを実際に取得して検証"""
    fetcher = CryptoPriceFetcher()
    df = fetcher.fetch_daily_data("BTC", days=5)

    assert not df.empty
    assert "Close" in df.columns
    assert "Date" in df.columns
    # BTC価格が1000ドル以上であること（極端な異常値でないこと）
    assert df.iloc[-1]["Close"] > 1000

def test_crypto_fetcher_metadata_real():
    """メタデータを実際に取得"""
    fetcher = CryptoPriceFetcher()
    info = fetcher.fetch_metadata("BTC")
    assert info != {}
    assert "market_cap" in info

def test_crypto_fetcher_invalid_symbol():
    """存在しない暗号資産シンボル"""
    fetcher = CryptoPriceFetcher()
    df = fetcher.fetch_daily_data("INVALID999", days=1)
    assert df.empty
