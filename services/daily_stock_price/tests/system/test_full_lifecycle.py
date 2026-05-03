from fastapi.testclient import TestClient

from src.api.app import app, get_engine
from src.catalog import CatalogManager
from src.engine import MarketDataEngine
from tests.conftest import FakeFetcher

# Constants for testing
STATUS_OK = 200
EXPECTED_PRICE_COUNT = 5

def test_full_system_handshake(temp_data_dir):
    """
    Tier 3: System Test.
    Simulates:
    1. CLI: uv run python main.py --sync MSFT
    2. API: uv run python main.py --api --port 9999
    (In tests, we use the library classes directly but follow the same flow)
    """
    # Setup isolated environment
    base_dir = temp_data_dir / "market_data"
    catalog_path = temp_data_dir / "catalog.sqlite"

    # 1. Simulate SYNC Phase
    # We skip external network by using class directly but with real logic flow
    fetcher = FakeFetcher()
    engine = MarketDataEngine(fetcher=fetcher, base_dir=str(base_dir))

    ticker = "SYSTEM_MSFT"
    engine.sync_ticker(ticker)

    # 2. Simulate API Phase
    # We verify the catalog was properly populated by the sync
    catalog = CatalogManager(db_path=catalog_path)
    assert len(catalog.get_paths(ticker)) == 1

    # 3. Simulate CONSUMPTION Phase via TestClient
    app.dependency_overrides[get_engine] = lambda: engine

    with TestClient(app) as client:
        response = client.get(f"/prices/{ticker}")
        assert response.status_code == STATUS_OK
        result = response.json()
        assert isinstance(result, list)
        assert result[0]["Ticker"] == ticker
        assert len(result) == EXPECTED_PRICE_COUNT

    app.dependency_overrides.clear()
