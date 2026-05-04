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

# yfinance internal exception might not be exposed, so we catch generic RateLimit or generic Exception
try:
    from yfinance.exceptions import YFRateLimitError
except ImportError:
    # Fallback if the specific exception is not found in the installed version
    class YFRateLimitError(Exception):
        pass

class YFinanceFetcher:
    """
    Yahoo Finance (yfinance) を使用して指数データを取得するフェッチャー。
    """

    @property
    def source_name(self) -> str:
        return "yfinance"

    @retry(
        wait=wait_exponential(multiplier=2, min=10, max=120),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((YFRateLimitError, Exception, RuntimeError)),
        reraise=True,
    )
    def _download_with_retry(self, ticker, start_date_str):
        df = yf.download(ticker, start=start_date_str, progress=False)
        if df is None or df.empty:
            # yfinance often returns empty instead of raising on rate limits
            raise RuntimeError(f"yfinance returned empty data for {ticker} (possible rate limit)")
        return df

    def fetch(self, ticker: str, start_date: datetime) -> pd.DataFrame:
        """
        指定されたティッカーのデータを開始日から現在まで取得する。
        """
        logger.info(f"Downloading {ticker} via yfinance starting from {start_date.date()}...")
        try:
            start_date_str = start_date.strftime("%Y-%m-%d")
            df = self._download_with_retry(ticker, start_date_str)
            
            if df.empty:
                logger.warning(f"yfinance returned empty data for {ticker}")
                return pd.DataFrame()

            # MultiIndex のフラット化 (単一銘柄でも階層化される場合があるため)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            return enforce_schema(df, ticker, self.source_name)
        except Exception as e:
            logger.error(f"yfinance error during fetch for {ticker}: {e}")
            return pd.DataFrame()
