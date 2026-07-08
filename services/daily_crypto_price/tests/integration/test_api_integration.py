from pathlib import Path

import main
import pytest
from fastapi.testclient import TestClient
from main import app
from src.engine.db_engine import CryptoDBEngine

# Constants for testing
STATUS_OK = 200
STATUS_NOT_FOUND = 404
STATUS_BAD_REQUEST = 400

# Use a separate test database
TEST_DB = "tests/integration_test.duckdb"


@pytest.fixture(scope="module")
def client():
    # Setup
    path = Path(TEST_DB)
    if path.exists():
        path.unlink()
    if path.exists():
        path.unlink()

    # Force app to use test DB via environment variable or monkeypatching
    original_db = main.db
    main.db = CryptoDBEngine(db_path=TEST_DB)

    with TestClient(app) as c:
        yield c

    # Teardown
    if path.exists():
        path.unlink()
    main.db = original_db


def test_api_root(client):
    response = client.get("/")
    assert response.status_code == STATUS_OK
    assert response.json()["message"] == "Daily Crypto Price API is running"


def test_api_get_prices_no_sync_not_found(client):
    response = client.get("/prices/UNKNOWN_COIN")
    assert response.status_code == STATUS_NOT_FOUND


def test_api_sync_flow_success(client):
    # This test will actually call yfinance
    response = client.get("/prices/BTC?sync=True")
    assert response.status_code == STATUS_OK
    data = response.json()
    assert "prices" in data
    assert "metadata" in data
    assert data["ticker"] == "BTC"
    assert len(data["prices"]) > 0
    assert data["metadata"]["circulating_supply"] > 0


def test_api_cached_data(client):
    # First call already synced BTC in previous test
    response = client.get("/prices/BTC?sync=False")
    assert response.status_code == STATUS_OK
    data = response.json()
    assert len(data["prices"]) > 0
    assert data["metadata"] is not None


def test_api_invalid_ticker_format(client):
    response = client.get("/prices/BTC!!$$")
    assert response.status_code == STATUS_BAD_REQUEST
    assert "Invalid ticker format" in response.json()["detail"]
