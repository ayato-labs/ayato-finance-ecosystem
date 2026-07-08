import logging
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# yfinance internal exception might not be exposed, so we catch generic RateLimit or generic Exception
try:
    from yfinance.exceptions import YFRateLimitError
except ImportError:
    # Fallback if the specific exception is not found in the installed version
    class YFRateLimitError(Exception):
        pass


class ForexFetcher:
    """
    yfinanceを使用して為替レートを取得し、USDを基準に正規化するフェッチャー。
    """

    def __init__(self):
        # Ticker mappings: (Symbol, is_inverse_to_usd)
        self.tickers = {
            "JPY": ("JPY=X", True),
            "EUR": ("EURUSD=X", False),
            "CNY": ("CNY=X", True),
        }

    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((YFRateLimitError, Exception)),
        reraise=True,
    )
    def _history_with_retry(self, ticker, start_date_str):
        return ticker.history(start=start_date_str, interval="1d")

    def fetch(self, symbol: str, start_date: datetime) -> pd.DataFrame:
        """
        指定された通貨の対米ドルレートを取得する。
        """
        if symbol == "USD":
            dates = pd.date_range(start=start_date, end=datetime.now(), freq="D")
            df = pd.DataFrame(
                {"Date": dates, "Symbol": "USD", "Rate": 1.0, "LoadTimestamp": datetime.now()}
            )
            return df

        if symbol not in self.tickers:
            logger.error(f"Unsupported currency symbol: {symbol}")
            return pd.DataFrame()

        ticker_symbol, is_inverse = self.tickers[symbol]
        fetch_start = start_date - timedelta(days=5)

        try:
            ticker = yf.Ticker(ticker_symbol)
            df = self._history_with_retry(ticker, fetch_start.strftime("%Y-%m-%d"))

            if df.empty:
                logger.warning(f"No data returned for {ticker_symbol}")
                return pd.DataFrame()

            # Clean and normalize
            df = df.reset_index()
            df = df[["Date", "Close"]].rename(columns={"Close": "Rate"})
            df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
            df["Symbol"] = symbol

            if is_inverse:
                df["Rate"] = 1.0 / df["Rate"]

            df["LoadTimestamp"] = datetime.now()
            df = df[df["Date"] >= pd.to_datetime(start_date)]

            return df
        except Exception as e:
            logger.error(f"Error fetching forex data for {symbol}: {e}")
            return pd.DataFrame()
