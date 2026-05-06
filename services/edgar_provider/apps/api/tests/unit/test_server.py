from fastapi.testclient import TestClient
from edgar_api.server import app
import pytest

client = TestClient(app)


def test_read_tickers_empty(monkeypatch):
    """API Unit Test: Verify /tickers behavior when DB might be empty or mocked."""
    # We could mock db_manager here if we wanted true unit isolation
    response = client.get("/tickers")
    # Even if empty, it should return 200 and a list
    assert response.status_code == 200
    assert "tickers" in response.json()


def test_financials_not_found():
    """API Unit Test: Verify 404 for non-existent ticker."""
    response = client.get("/financials/NONEXISTENT_TICKER_123")
    assert response.status_code == 404
