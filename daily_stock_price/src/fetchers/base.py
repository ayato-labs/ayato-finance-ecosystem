from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd


class BaseFetcher(ABC):
    """
    Abstract Base Class for market data fetchers.
    Any new data source (J-Quants, Bloomberg, etc.) should implement this interface.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """
        Returns the name of the data source (e.g., 'yfinance', 'jquants').
        Used for the 'Source' column in the database.
        """
        pass

    @abstractmethod
    def fetch(self, ticker: str, start_date: datetime) -> pd.DataFrame:
        """
        Fetches daily stock price data for a given ticker starting from start_date.
        """
        pass

    @abstractmethod
    def fetch_batch(self, tickers: list[str], start_date: datetime) -> pd.DataFrame:
        """
        Fetches daily stock price data for multiple tickers in a single operation.
        Returns a single combined DataFrame with all tickers.
        """
        pass
