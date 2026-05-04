from __future__ import annotations

import asyncio
import math
from datetime import datetime, timedelta
from typing import Any

import httpx
from loguru import logger

# Constants
HTTP_OK = 200
HTTP_NOT_FOUND = 404
DEFAULT_TIMEOUT = 10.0


class ExternalApiAggregator:
    def __init__(
        self,
        price_api_url: str,
        financials_api_url: str,
        index_api_url: str,
        macro_api_url: str,
        forex_api_url: str,
        crypto_api_url: str,
    ):
        self.price_api_url = price_api_url
        self.financials_api_url = financials_api_url
        self.index_api_url = index_api_url
        self.macro_api_url = macro_api_url
        self.forex_api_url = forex_api_url
        self.crypto_api_url = crypto_api_url
        logger.info(
            f"ExternalApiAggregator initialized with URLs: "
            f"Price={price_api_url}, Financials={financials_api_url}, "
            f"Index={index_api_url}, Macro={macro_api_url}, "
            f"Forex={forex_api_url}, Crypto={crypto_api_url}"
        )

    async def get_latest_price(self, ticker: str, asset_type: str = "STOCK") -> float | None:
        """Fetch the latest price. Redirects to appropriate API based on ticker and asset type."""
        if ticker.startswith("^"):
            base_url = self.index_api_url
        elif asset_type == "CRYPTO":
            base_url = self.crypto_api_url
        else:
            base_url = self.price_api_url

        url = f"{base_url}/prices/{ticker}"
        logger.info(f"Fetching latest price for {ticker} from {url}...")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=DEFAULT_TIMEOUT)
                if response.status_code == HTTP_NOT_FOUND:
                    logger.warning(f"Ticker {ticker} not found in price database.")
                    return None
                response.raise_for_status()
                data = response.json()
                if not data:
                    return None

                # Support both list-style (legacy) and object-style responses
                records = data["prices"] if isinstance(data, dict) and "prices" in data else data

                if not records or not isinstance(records, list):
                    return None

                # The API returns a list of records sorted by date. Get the last one.
                return records[-1].get("Close")
        except Exception as e:
            logger.exception(f"Unexpected error fetching latest price for {ticker}: {e}")
            return None

    async def get_historical_prices(self, ticker: str, days: int = 365) -> list[float]:
        """Fetch historical close prices for last N days.
        Redirects to index API if ticker starts with ^.
        """
        data = await self.get_historical_data_raw(ticker)
        if not data:
            return []

        # Sort and filter by date
        data.sort(key=lambda x: x["Date"])
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        prices = [
            d.get("Close") for d in data if d["Date"] >= cutoff and d.get("Close") is not None
        ]

        # If no data in period, fallback to all data to avoid errors
        if not prices and data:
            prices = [d.get("Close") for d in data if d.get("Close") is not None]

        return prices

    async def get_historical_data_raw(
        self, ticker: str, asset_type: str = "STOCK"
    ) -> list[dict[str, Any]]:
        """Fetch full historical records (OHLCV). Redirects to appropriate API."""
        if ticker.startswith("^"):
            base_url = self.index_api_url
        elif asset_type == "CRYPTO":
            base_url = self.crypto_api_url
        else:
            base_url = self.price_api_url

        url = f"{base_url}/prices/{ticker}"
        logger.info(f"Fetching raw historical data for {ticker} from {url}...")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=DEFAULT_TIMEOUT)
                if response.status_code == HTTP_NOT_FOUND:
                    return []
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict) and "prices" in data:
                    return data["prices"]
                return data
        except Exception as e:
            logger.exception(f"Unexpected error fetching raw historical data for {ticker}: {e}")
            return []

    async def get_benchmark_performance(self, ticker: str) -> float:
        """Calculate performance from historical data (Last 1 Year)."""
        data = await self.get_historical_data_raw(ticker)
        if not data:
            return 0.0

        # Sort by date and filter to last 365 days
        data.sort(key=lambda x: x["Date"])
        one_year_ago = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        filtered = [d for d in data if d["Date"] >= one_year_ago]
        if len(filtered) < 2:
            # Fallback to last 260 trading days if 365 calendar days is too restrictive
            filtered = data[-260:] if len(data) >= 2 else data

        if len(filtered) < 2:
            return 0.0

        start_price = filtered[0].get("Close") or 0
        end_price = filtered[-1].get("Close") or 0

        if start_price == 0:
            return 0.0

        return ((end_price - start_price) / start_price) * 100

    async def get_financial_health(self, ticker: str) -> float | None:
        """
        Placeholder for financial health.
        The current API provides raw financials via /financials/{ticker}.
        """
        url = f"{self.financials_api_url}/financials/{ticker}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=DEFAULT_TIMEOUT)
                if response.status_code == HTTP_NOT_FOUND:
                    return None
                response.raise_for_status()
                # For now, return a placeholder score if data exists
                data = response.json()
                return 80.0 if data else None
        except Exception as e:
            logger.exception(f"Unexpected error fetching financials for {ticker}: {e}")
            return None

    async def get_latest_macro_value(self, symbol: str) -> float | None:
        """Fetch the latest value for a macro indicator from port 5010."""
        url = f"{self.macro_api_url}/indicators/{symbol}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=DEFAULT_TIMEOUT)
                if response.status_code == HTTP_NOT_FOUND:
                    return None
                response.raise_for_status()
                data = response.json()
                if not data:
                    return None

                # Get the latest value from the history
                latest_record = data[-1]
                val = latest_record.get("Value")
                if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
                    return None
                return val
        except Exception as e:
            logger.exception(f"Unexpected error fetching macro indicator {symbol}: {e}")
            return None

    async def get_latest_exchange_rate(self, symbol: str) -> float | None:
        """
        Fetch the latest exchange rate from port 5011.
        Returns value as '1 Unit = X USD'.
        Example: JPY -> 0.0065
        """
        if not symbol:
            return None
        if symbol.upper() == "USD":
            return 1.0

        url = f"{self.forex_api_url}/latest/{symbol.upper()}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=DEFAULT_TIMEOUT)
                if response.status_code == HTTP_NOT_FOUND:
                    logger.warning(f"Forex symbol {symbol} not found.")
                    return None
                response.raise_for_status()
                data = response.json()
                # API returns {"symbol": "...", "rate": ...}
                val = data.get("rate")
                if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
                    return None
                return val
        except Exception as e:
            logger.exception(f"Unexpected error fetching exchange rate for {symbol}: {e}")
            return None

    async def enrich_asset_data(self, ticker: str, asset_type: str = "STOCK") -> dict[str, Any]:
        logger.info(f"Enriching asset data for {ticker} ({asset_type})...")

        # Base tasks
        price_task = asyncio.create_task(self.get_latest_price(ticker, asset_type))
        health_task = asyncio.create_task(self.get_financial_health(ticker))

        # Crypto specific metadata
        crypto_meta = None
        if asset_type == "CRYPTO":
            url = f"{self.crypto_api_url}/prices/{ticker}"
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, timeout=DEFAULT_TIMEOUT)
                    if resp.status_code == HTTP_OK:
                        data = resp.json()
                        if isinstance(data, dict) and "metadata" in data:
                            crypto_meta = data["metadata"]
            except Exception as e:
                logger.warning(f"Failed to fetch crypto metadata for {ticker}: {e}")

        price, health = await asyncio.gather(price_task, health_task)

        return {
            "ticker": ticker,
            "current_price": price,
            "financial_health": health,
            "crypto_metadata": crypto_meta,
        }
