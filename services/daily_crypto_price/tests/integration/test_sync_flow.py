from pathlib import Path
from unittest.mock import patch

import pytest

from src.engine.db_engine import CryptoDBEngine
from src.fetchers.crypto_fetcher import CryptoPriceFetcher

# Constants for testing
MIN_EXPECTED_PRICE_COUNT = 2
FETCH_DAYS = 2


@pytest.fixture
def integration_context():
    db_path = "tests/integration_crypto.duckdb"
    path = Path(db_path)
    if path.exists():
        path.unlink()
    db = CryptoDBEngine(db_path=db_path)
    fetcher = CryptoPriceFetcher()
    yield fetcher, db
    if path.exists():
        path.unlink()


def test_fetch_and_save_flow(integration_context):
    fetcher, db = integration_context
    ticker = "ETH"

    # 1. Fetch real data (Integration test with real service)
    df = fetcher.fetch_daily_data(ticker, days=FETCH_DAYS)
    assert not df.empty

    # 2. Save to DB
    db.save_prices(ticker, df)

    # 3. Retrieve and verify
    saved_data = db.get_prices(ticker)
    assert len(saved_data) >= MIN_EXPECTED_PRICE_COUNT
    assert saved_data[0]["ticker"] == ticker


@patch("yfinance.download")
def test_sync_with_mocked_external_error(mock_yf, integration_context):
    fetcher, db = integration_context
    # Simulate yfinance failure
    mock_yf.side_effect = Exception("API Down")

    df = fetcher.fetch_daily_data("BTC", days=1)
    assert df.empty

    # Ensure nothing was saved incorrectly
    saved_data = db.get_prices("BTC")
    assert len(saved_data) == 0
