import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app

# Create a separate test database for E2E
os.environ["DATABASE_PATH"] = "tests/e2e_crypto.duckdb"

@pytest.fixture
def client():
    # Setup test DB
    db_path = os.environ["DATABASE_PATH"]
    path = Path(db_path)
    if path.exists():
        path.unlink()
    
    with TestClient(app) as c:
        yield c
    
    if path.exists():
        path.unlink()

def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "Daily Crypto Price API is running"

def test_get_prices_success(client):
    # Fetch real BTC data via API
    response = client.get("/prices/BTC?sync=true")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "prices" in data
    assert "metadata" in data
    assert len(data["prices"]) > 0
    assert "Close" in data["prices"][0]

def test_get_prices_not_found(client):
    # Test ticker that exists in format but has no data
    response = client.get("/prices/NONEXISTENT?sync=true")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]

def test_get_prices_no_sync(client):
    # First sync to populate
    client.get("/prices/DOGE?sync=true")
    
    # Then get without sync (should be fast and from DB)
    response = client.get("/prices/DOGE?sync=false")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert len(data["prices"]) > 0
