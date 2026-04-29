from pathlib import Path
from unittest import mock

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import main
import src.fetchers.crypto_fetcher as fetcher_mod
from main import app
from src.engine.db_engine import CryptoDBEngine

# Constants for testing
STATUS_OK = 200
STATUS_NOT_FOUND = 404
EXPECTED_PARTIAL_COUNT = 1

@pytest.fixture
def client():
    db_path = "tests/e2e_test.duckdb"
    path = Path(db_path)
    if path.exists():
        path.unlink()

    original_db = main.db
    main.db = CryptoDBEngine(db_path=db_path)
    with TestClient(app) as c:
        yield c

    if path.exists():
        path.unlink()
    main.db = original_db

def test_full_sync_and_retrieval_flow(client):
    """
    Scenario: User requests BTC for the first time with sync.
    Expect: Metadata and prices are fetched and stored.
    """
    # 1. Sync
    resp = client.get("/prices/BTC?sync=True")
    assert resp.status_code == STATUS_OK

    # 2. Verify subsequent call returns from DB (fast)
    resp_cached = client.get("/prices/BTC?sync=False")
    assert resp_cached.status_code == STATUS_OK
    assert resp.json() == resp_cached.json()

def test_system_handles_fetcher_failure(client):
    """
    Scenario: YFinance fails (network down).
    Expect: System returns 404 if no data in DB, or cached data if exists.
    """
    # Mock fetch_daily_data to raise exception
    with mock.patch.object(
        fetcher_mod.CryptoPriceFetcher, "fetch_daily_data", side_effect=Exception("Network Error")
    ):
        resp = client.get("/prices/ETH?sync=True")
        # Should fail to sync but try to get from DB. DB is empty, so 404.
        assert resp.status_code == STATUS_NOT_FOUND

def test_system_handles_partial_data(client):
    """
    Scenario: Prices are fetched but metadata fails.
    Expect: Prices are returned, metadata is null.
    """
    mock_df = pd.DataFrame({
        "Date": ["2023-01-01"], "Open": [1.0], "High": [1.1],
        "Low": [0.9], "Close": [1.0], "Volume": [100]
    })

    with (
        mock.patch.object(fetcher_mod.CryptoPriceFetcher, "fetch_daily_data", return_value=mock_df),
        mock.patch.object(fetcher_mod.CryptoPriceFetcher, "fetch_metadata", return_value={}),
    ):
        resp = client.get("/prices/PARTIAL_TEST?sync=True")
        assert resp.status_code == STATUS_OK
        data = resp.json()
        assert len(data["prices"]) == EXPECTED_PARTIAL_COUNT
        assert data["metadata"] is None

def test_strict_invalid_data_handling(client):
    """
    Scenario: Ticker exists but yfinance returns empty results.
    Expect: 404 with appropriate message.
    """
    # Ticker format is valid but it's a "ghost" ticker
    resp = client.get("/prices/GHOSTCOIN?sync=True")
    assert resp.status_code == STATUS_NOT_FOUND
    assert "not found" in resp.json()["detail"]
