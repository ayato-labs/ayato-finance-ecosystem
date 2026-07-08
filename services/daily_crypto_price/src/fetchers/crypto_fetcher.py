from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# yfinance internal exception might not be exposed, so we catch generic RateLimit or generic Exception
try:
    from yfinance.exceptions import YFRateLimitError
except ImportError:
    # Fallback if the specific exception is not found in the installed version
    class YFRateLimitError(Exception):
        pass


class CryptoPriceFetcher:
    def __init__(self):
        pass

    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((YFRateLimitError, Exception)),
        reraise=True,
    )
    def _download_with_retry(self, yf_symbol, start_date):
        return yf.download(yf_symbol, start=start_date, progress=False)

    def fetch_daily_data(self, symbol: str, days: int = 365) -> pd.DataFrame:
        """
        Fetches daily OHLCV data for a crypto symbol from Yahoo Finance.
        e.g., BTC -> BTC-USD
        """
        yf_symbol = f"{symbol}-USD" if "-" not in symbol else symbol
        logger.info(f"Fetching {days} days of data for {yf_symbol}...")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        try:
            df = self._download_with_retry(yf_symbol, start_date)
            if df.empty:
                logger.warning(f"No data found for {yf_symbol}")
                return pd.DataFrame()

            # Clean columns (Handle MultiIndex if necessary)
            if isinstance(df.columns, pd.MultiIndex):
                df = df.stack(level=1, future_stack=True).reset_index(level=1, drop=True)

            df = df.reset_index()
            df = df.rename(
                columns={
                    "Date": "Date",
                    "Close": "Close",
                    "Open": "Open",
                    "High": "High",
                    "Low": "Low",
                    "Volume": "Volume",
                }
            )

            df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
            df = df.dropna(subset=["Close"])
            df = df.fillna(0.0)
            df = df[df["Close"] > 0]

            return df[["Date", "Open", "High", "Low", "Close", "Volume"]]
        except Exception as e:
            logger.error(f"Unexpected error fetching data for {yf_symbol}: {e}")
            return pd.DataFrame()

    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((YFRateLimitError, Exception)),
        reraise=True,
    )
    def _get_info_with_retry(self, ticker):
        return ticker.info

    def fetch_metadata(self, symbol: str) -> dict:
        """
        Fetches metadata (supply, market cap, description) for a crypto symbol from Yahoo Finance.
        """
        yf_symbol = f"{symbol}-USD" if "-" not in symbol else symbol
        logger.info(f"Fetching metadata for {yf_symbol}...")
        try:
            ticker = yf.Ticker(yf_symbol)
            info = self._get_info_with_retry(ticker)

            if not info:
                logger.warning(f"No metadata found for {yf_symbol}")
                return {}

            return {
                "circulating_supply": info.get("circulatingSupply"),
                "total_supply": info.get("totalSupply"),
                "max_supply": info.get("maxSupply"),
                "market_cap": info.get("marketCap"),
                "description": info.get("description"),
            }
        except Exception as e:
            logger.error(f"Unexpected error fetching metadata for {yf_symbol}: {e}")
            return {}
