from __future__ import annotations

import httpx
import pytest
import respx

from core.aggregator import ExternalApiAggregator
from core.config import settings


@pytest.mark.asyncio
async def test_aggregator_handles_crypto_object_response():
    aggregator = ExternalApiAggregator(
        price_api_url="http://p",
        financials_api_url="http://f",
        index_api_url="http://i",
        macro_api_url="http://m",
        forex_api_url="http://x",
        crypto_api_url=settings.crypto_api_url,
    )

    mock_response = {
        "ticker": "BTC",
        "prices": [{"Date": "2023-01-01", "Close": 30000.0}],
        "metadata": {"circulating_supply": 19000000.0},
    }

    with respx.mock:
        respx.get(f"{settings.crypto_api_url}/prices/BTC").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        price = await aggregator.get_latest_price("BTC", asset_type="CRYPTO")
        assert price == 30000.0

        # Test enrichment
        respx.get("http://f/financials/BTC").mock(return_value=httpx.Response(404))
        enriched = await aggregator.enrich_asset_data("BTC", asset_type="CRYPTO")
        assert enriched["crypto_metadata"]["circulating_supply"] == 19000000.0


@pytest.mark.asyncio
async def test_aggregator_handles_legacy_list_response():
    aggregator = ExternalApiAggregator(
        price_api_url="http://p",
        financials_api_url="http://f",
        index_api_url="http://i",
        macro_api_url="http://m",
        forex_api_url="http://x",
        crypto_api_url="http://c",
    )

    # Legacy format just returned a list of prices
    mock_response = [{"Date": "2023-01-01", "Close": 150.0}]

    with respx.mock:
        respx.get("http://p/prices/AAPL").mock(return_value=httpx.Response(200, json=mock_response))

        price = await aggregator.get_latest_price("AAPL", asset_type="STOCK")
        assert price == 150.0


@pytest.mark.asyncio
async def test_aggregator_handles_api_error_gracefully():
    aggregator = ExternalApiAggregator(
        price_api_url="http://p",
        financials_api_url="http://f",
        index_api_url="http://i",
        macro_api_url="http://m",
        forex_api_url="http://x",
        crypto_api_url=settings.crypto_api_url,
    )

    with respx.mock:
        respx.get(f"{settings.crypto_api_url}/prices/FAIL").mock(return_value=httpx.Response(500))

        price = await aggregator.get_latest_price("FAIL", asset_type="CRYPTO")
        assert price is None

        enriched = await aggregator.enrich_asset_data("FAIL", asset_type="CRYPTO")
        assert enriched["current_price"] is None
        assert enriched["crypto_metadata"] is None


@pytest.mark.asyncio
async def test_aggregator_multi_api_flow():
    aggregator = ExternalApiAggregator(
        price_api_url="http://p",
        financials_api_url="http://f",
        index_api_url="http://i",
        macro_api_url="http://m",
        forex_api_url="http://x",
        crypto_api_url="http://c",
    )

    with respx.mock:
        respx.get("http://i/prices/%5EGSPC").mock(
            return_value=httpx.Response(
                200, json={"prices": [{"Date": "2023-01-01", "Close": 4000}]}
            )
        )
        respx.get("http://m/indicators/FED_FUNDS").mock(
            return_value=httpx.Response(200, json=[{"Date": "2023-01-01", "Value": 5.25}])
        )
        respx.get("http://x/latest/JPY").mock(
            return_value=httpx.Response(200, json={"rate": 150.0})
        )

        index_data = await aggregator.get_historical_data_raw("^GSPC")
        assert index_data[0]["Close"] == 4000

        fed_rate = await aggregator.get_latest_macro_value("FED_FUNDS")
        assert fed_rate == 5.25

        forex_rate = await aggregator.get_latest_exchange_rate("JPY")
        assert forex_rate == 150.0


@pytest.mark.asyncio
async def test_aggregator_timeout_handling():
    aggregator = ExternalApiAggregator(
        price_api_url="http://p",
        financials_api_url="http://f",
        index_api_url="http://i",
        macro_api_url="http://m",
        forex_api_url="http://x",
        crypto_api_url="http://c",
    )

    with respx.mock:
        # Simulate timeout
        respx.get("http://p/prices/SLOW").mock(side_effect=httpx.TimeoutException("Timeout"))

        price = await aggregator.get_latest_price("SLOW", asset_type="STOCK")
        assert price is None
