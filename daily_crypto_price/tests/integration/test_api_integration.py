from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.engine.db_engine import CryptoDBEngine

# Use a separate test database
TEST_DB = "tests/integration_test.duckdb"

@pytest.fixture(scope="module")
def client():
    # Setup
    path = Path(TEST_DB)
    if path.exists():
        path.unlink()
    
    # Force app to use test DB via environment variable or monkeypatching
    import main
    from main import app
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
    assert response.status_code == 200
    assert response.json()["message"] == "Daily Crypto Price API is running"

def test_api_get_prices_no_sync_not_found(client):
    response = client.get("/prices/UNKNOWN_COIN")
    assert response.status_code == 404

def test_api_sync_flow_success(client):
    # This test will actually call yfinance
    response = client.get("/prices/BTC?sync=True")
    assert response.status_code == 200
    data = response.json()
    assert "prices" in data
    assert "metadata" in data
    assert data["ticker"] == "BTC"
    assert len(data["prices"]) > 0
    assert data["metadata"]["circulating_supply"] > 0

def test_api_cached_data(client):
    # First call already synced BTC in previous test
    response = client.get("/prices/BTC?sync=False")
    assert response.status_code == 200
    data = response.json()
    assert len(data["prices"]) > 0
    assert data["metadata"] is not None

def test_api_invalid_ticker_format(client):
    response = client.get("/prices/BTC!!$$")
    assert response.status_code == 400
    assert "Invalid ticker format" in response.json()["detail"]
