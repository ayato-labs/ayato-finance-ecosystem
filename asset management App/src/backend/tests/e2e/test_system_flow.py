from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from core.database import DatabaseManager
from core.models import AssetType, Transaction, TransactionType
from main import app


@pytest.fixture
def client():
    # Setup test DB for main backend
    test_db = Path("tests/e2e_assets.duckdb")
    if test_db.exists():
        test_db.unlink()

    # Environment variable for DB path
    os.environ["DATABASE_PATH"] = str(test_db)

    import main

    # Refresh DB manager to use the new path
    main.db = DatabaseManager(db_path=str(test_db))

    # Add a dummy transaction for testing
    main.db.add_transaction(
        Transaction(
            ticker="BTC",
            type=TransactionType.BUY,
            asset_type=AssetType.CRYPTO,
            quantity=0.1,
            price=30000.0,
            currency="USD",
            timestamp=datetime.now(),
        )
    )

    with TestClient(app) as c:
        yield c

    if test_db.exists():
        test_db.unlink()
    del os.environ["DATABASE_PATH"]


def test_portfolio_endpoint_full_flow(client):
    """
    Test the main /portfolio endpoint.
    Mocks external APIs to avoid actual network calls in E2E backend test.
    """
    with (
        mock.patch("core.aggregator.ExternalApiAggregator.get_latest_price", return_value=40000.0),
        mock.patch(
            "core.aggregator.ExternalApiAggregator.get_benchmark_performance", return_value=10.0
        ),
        mock.patch(
            "core.aggregator.ExternalApiAggregator.get_latest_macro_value", return_value=4.5
        ),
        mock.patch(
            "core.aggregator.ExternalApiAggregator.get_historical_data_raw", return_value=[]
        ),
        mock.patch(
            "core.aggregator.ExternalApiAggregator.get_latest_exchange_rate", return_value=1.0
        ),
    ):
        response = client.get("/portfolio?currency=USD")
        assert response.status_code == 200
        data = response.json()

        assert data["total_market_value"] == 4000.0  # 0.1 * 40000
        assert len(data["assets"]) == 1
        assert data["assets"][0]["ticker"] == "BTC"
        assert data["assets"][0]["asset_type"] == "CRYPTO"


def test_portfolio_handles_missing_aggregator_data(client):
    """
    Scenario: Aggregator fails to fetch price.
    Expect: Portfolio still calculates based on average cost or returns zero gain.
    """
    with mock.patch("core.aggregator.ExternalApiAggregator.get_latest_price", return_value=None):
        response = client.get("/portfolio?currency=USD")
        assert response.status_code == 200
        data = response.json()
        # Should still return asset list but maybe with 0 market value or fallback
        assert len(data["assets"]) == 1
