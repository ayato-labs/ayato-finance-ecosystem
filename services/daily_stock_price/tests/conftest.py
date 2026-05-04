from datetime import datetime

import pandas as pd
import pytest

from src.catalog import CatalogManager
from src.engine import MarketDataEngine


class FakeFetcher:
    """A deterministic, zero-dependency source for unit testing. No MagicMock used."""

    def __init__(self, data_map=None):
        # Allow pre-defining data for specific tickers
        self.data_map = data_map or {}
        self.source_name = "fake_source"

    def fetch(self, ticker, start_date=None):
        if ticker in self.data_map:
            return self.data_map[ticker]

        # Default mock-like but concrete data
        dates = pd.date_range(start="2024-01-01", periods=5, freq="D")
        data = {
            "Date": dates,
            "Ticker": [ticker] * 5,
            "Open": [100.0] * 5,
            "High": [105.0] * 5,
            "Low": [95.0] * 5,
            "Close": [102.0] * 5,
            "Volume": [1000] * 5,
            "StockSplits": [0.0] * 5,
            "Source": ["fake"] * 5,
            "LoadTimestamp": [datetime.now()] * 5,
        }
        return pd.DataFrame(data)


@pytest.fixture
def fake_fetcher():
    return FakeFetcher()


@pytest.fixture
def temp_data_dir(tmp_path):
    """Creates a strictly isolated temporary directory for each test."""
    d = tmp_path / "data"
    d.mkdir()
    (d / "market_data").mkdir()
    return d


@pytest.fixture
def temp_catalog(temp_data_dir):
    """Provides a fresh, isolated SQLite catalog for each test."""
    db_path = temp_data_dir / "catalog.sqlite"
    return CatalogManager(db_path=db_path)


@pytest.fixture
def engine(temp_data_dir, fake_fetcher):
    """Provides an isolated MarketDataEngine instance using the FakeFetcher."""
    return MarketDataEngine(fetcher=fake_fetcher, base_dir=str(temp_data_dir / "market_data"))
