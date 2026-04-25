import logging
from datetime import datetime

import pandas as pd
import yfinance as yf

from ..schema import enforce_schema
from .base import BaseFetcher

logger = logging.getLogger(__name__)


class YFinanceFetcher(BaseFetcher):
    """
    Implementation of BaseFetcher using the yfinance library.
    """

    @property
    def source_name(self) -> str:
        return "yfinance"

    def fetch(self, ticker: str, start_date: datetime) -> pd.DataFrame:
        """
        Fetches data from Yahoo Finance via yfinance.
        """
        logger.info(f"Downloading {ticker} via yfinance starting from {start_date.date()}...")
        try:
            df = yf.download(
                ticker, 
                start=start_date.strftime("%Y-%m-%d"), 
                progress=False, 
                actions=True
            )
            if df.empty:
                logger.warning(f"yfinance returned empty data for {ticker}")
                return pd.DataFrame()

            # Column cleaning (Flattening MultiIndex if necessary for single ticker)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            if "Stock Splits" in df.columns:
                df = df.rename(columns={"Stock Splits": "StockSplits"})

            # Internal schema enforcement
            return enforce_schema(df, ticker, self.source_name)
        except Exception as e:
            logger.error(f"yfinance error during fetch for {ticker}: {e}")
            raise  # Propagate up for traceability logging

    def fetch_batch(self, tickers: list[str], start_date: datetime) -> pd.DataFrame:
        """
        Fetches data for multiple tickers in a single yfinance request.
        """
        if not tickers:
            return pd.DataFrame()

        logger.info(
            f"Downloading batch of {len(tickers)} tickers via yfinance starting from {start_date.date()}..."
        )
        try:
            # yfinance returns MultiIndex (Metric, Ticker) when multiple tickers are passed
            df = yf.download(
                tickers, 
                start=start_date.strftime("%Y-%m-%d"), 
                progress=False, 
                group_by="column",
                actions=True
            )

            if df.empty:
                logger.warning(f"yfinance returned empty data for batch: {tickers[:5]}...")
                return pd.DataFrame()

            # Rename "Stock Splits" to "StockSplits" in MultiIndex level 0
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.set_levels(
                    df.columns.levels[0].str.replace("Stock Splits", "StockSplits"), level=0
                )

            # yfinance returns a DataFrame with MultiIndex columns (Metric, Ticker)
            stacked = df.stack(level=1, future_stack=True)
            stacked.index.names = ["Date", "Ticker"]
            stacked = stacked.reset_index()

            all_dfs = []
            for ticker, group in stacked.groupby("Ticker"):
                ticker_str = str(ticker)
                clean_group = group.drop(columns=["Ticker"])
                # We want to skip tickers that are all-NaN in the batch result
                if clean_group["Close"].isnull().all():
                    continue
                all_dfs.append(enforce_schema(clean_group, ticker_str, self.source_name))

            if not all_dfs:
                return pd.DataFrame()

            return pd.concat(all_dfs, ignore_index=True)

        except Exception as e:
            logger.error(f"yfinance error during batch fetch: {e}")
            raise  # Propagate up for traceability logging


