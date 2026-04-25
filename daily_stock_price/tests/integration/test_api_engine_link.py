import pytest
from fastapi.testclient import TestClient
from src.api.app import app, get_engine
from src.engine import MarketDataEngine

# Define a temporary engine for the API tests
@pytest.fixture
def api_client(engine):
    # Override the dependency to use the isolated engine fixture
    app.dependency_overrides[get_engine] = lambda: engine
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()

def test_api_status_endpoint(api_client):
    """Verify common status endpoint."""
    response = api_client.get("/")
    assert response.status_code == 200
    assert "Daily Stock Price API" in response.json()["message"]

def test_api_prices_fetch(api_client, engine):
    """Verify /prices/{ticker} endpoint correctly triggers engine view generation."""
    ticker = "API_TEST"
    engine.sync_ticker(ticker) # Seed data
    
    response = api_client.get(f"/prices/{ticker}")
    assert response.status_code == 200
    data = response.json()
    
    assert isinstance(data, list)
    assert len(data) == 5
    assert "Close" in data[0]
    assert "StockSplits" in data[0]

def test_api_nonexistent_ticker(api_client):
    """Verify 404 behavior for unknown tickers."""
    response = api_client.get("/prices/UNKNOWN_ERROR")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
