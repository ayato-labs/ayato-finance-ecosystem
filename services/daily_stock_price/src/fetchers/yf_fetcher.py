from datetime import datetime
import pandas as pd
import yfinance as yf
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from ..schema import enforce_schema
from .base import BaseFetcher

# yfinance internal exception might not be exposed, so we catch generic RateLimit or generic Exception
try:
    from yfinance.exceptions import YFRateLimitError
except ImportError:
    # Fallback if the specific exception is not found in the installed version
    class YFRateLimitError(Exception):
        pass

class YFinanceFetcher(BaseFetcher):
    """
    Implementation of BaseFetcher using the yfinance library.
    """

    @property
    def source_name(self) -> str:
        return "yfinance"

    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((YFRateLimitError, Exception)),
        reraise=True,
    )
    def _download_with_retry(self, ticker, start_date_str, **kwargs):
        return yf.download(ticker, start=start_date_str, progress=False, **kwargs)

    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((YFRateLimitError, Exception)),
        reraise=True,
    )
    def _get_info_with_retry(self, ticker_obj):
        return ticker_obj.info

    def fetch(self, ticker: str, start_date: datetime) -> pd.DataFrame:
        """
        Fetches data from Yahoo Finance via yfinance.
        """
        logger.info(f"Downloading {ticker} via yfinance starting from {start_date.date()}...")
        try:
            start_date_str = start_date.strftime("%Y-%m-%d")
            df = self._download_with_retry(ticker, start_date_str, actions=True)
            
            if df.empty:
                logger.warning(f"yfinance returned empty data for {ticker}")
                return pd.DataFrame()

            # Column cleaning
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            if "Stock Splits" in df.columns:
                df = df.rename(columns={"Stock Splits": "StockSplits"})

            # Fetch SharesOutstanding from info
            try:
                ticker_obj = yf.Ticker(ticker)
                info = self._get_info_with_retry(ticker_obj)
                shares = info.get("sharesOutstanding")
                df["SharesOutstanding"] = shares
            except Exception as e:
                logger.warning(f"Could not fetch sharesOutstanding for {ticker}: {e}")
                df["SharesOutstanding"] = None

            return enforce_schema(df, ticker, self.source_name)
        except Exception as e:
            logger.error(f"yfinance error during fetch for {ticker}: {e}")
            raise

    def fetch_batch(self, tickers: list[str], start_date: datetime) -> pd.DataFrame:
        """
        Fetches data for multiple tickers in a single yfinance request.
        """
        if not tickers:
            return pd.DataFrame()

        logger.info(
            f"Downloading batch of {len(tickers)} tickers via yfinance "
            f"starting from {start_date.date()}..."
        )
        try:
            start_date_str = start_date.strftime("%Y-%m-%d")
            df = self._download_with_retry(
                tickers, 
                start_date_str, 
                group_by="column",
                actions=True
            )

            if df.empty:
                logger.warning(f"yfinance returned empty data for batch: {tickers[:5]}...")
                return pd.DataFrame()

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.set_levels(
                    df.columns.levels[0].str.replace("Stock Splits", "StockSplits"), level=0
                )

            stacked = df.stack(level=1, future_stack=True)
            stacked.index.names = ["Date", "Ticker"]
            stacked = stacked.reset_index()

            all_dfs = []
            for ticker, group in stacked.groupby("Ticker"):
                ticker_str = str(ticker)
                clean_group = group.drop(columns=["Ticker"])
                if clean_group["Close"].isnull().all():
                    continue
                all_dfs.append(enforce_schema(clean_group, ticker_str, self.source_name))

            if not all_dfs:
                return pd.DataFrame()

            return pd.concat(all_dfs, ignore_index=True)

        except Exception as e:
            logger.error(f"yfinance error during batch fetch: {e}")
            raise
