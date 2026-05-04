import logging
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class ForexFetcher:
    """
    yfinanceを使用して為替レートを取得し、USDを基準に正規化するフェッチャー。
    """

    def __init__(self):
        # Ticker mappings: (Symbol, is_inverse_to_usd)
        # yfinance JPY=X gives USD/JPY (How many JPY for 1 USD)
        # yfinance EURUSD=X gives EUR/USD (How many USD for 1 EUR)
        # yfinance CNY=X gives USD/CNY (How many CNY for 1 USD)
        self.tickers = {
            "JPY": ("JPY=X", True),
            "EUR": ("EURUSD=X", False),
            "CNY": ("CNY=X", True),
        }

    def fetch(self, symbol: str, start_date: datetime) -> pd.DataFrame:
        """
        指定された通貨の対米ドルレートを取得する。
        返されるレートは '1 ForeignUnit = X USD' の形式。
        """
        if symbol == "USD":
            # USD case: static rate 1.0
            dates = pd.date_range(start=start_date, end=datetime.now(), freq="D")
            df = pd.DataFrame(
                {"Date": dates, "Symbol": "USD", "Rate": 1.0, "LoadTimestamp": datetime.now()}
            )
            return df

        if symbol not in self.tickers:
            logger.error(f"Unsupported currency symbol: {symbol}")
            return pd.DataFrame()

        ticker_symbol, is_inverse = self.tickers[symbol]

        # Adjust start date to ensure we get some data (yfinance sometimes misses the exact start)
        fetch_start = start_date - timedelta(days=5)

        try:
            ticker = yf.Ticker(ticker_symbol)
            df = ticker.history(start=fetch_start.strftime("%Y-%m-%d"), interval="1d")

            if df.empty:
                logger.warning(f"No data returned for {ticker_symbol}")
                return pd.DataFrame()

            # Clean and normalize
            df = df.reset_index()
            df = df[["Date", "Close"]].rename(columns={"Close": "Rate"})
            df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
            df["Symbol"] = symbol

            # Normalize to '1 ForeignUnit = X USD'
            if is_inverse:
                # USD/JPY -> 1 JPY = 1 / X USD
                df["Rate"] = 1.0 / df["Rate"]

            df["LoadTimestamp"] = datetime.now()

            # Filter to requested period
            df = df[df["Date"] >= pd.to_datetime(start_date)]

            return df
        except Exception as e:
            logger.error(f"Error fetching forex data for {symbol}: {e}")
            return pd.DataFrame()
