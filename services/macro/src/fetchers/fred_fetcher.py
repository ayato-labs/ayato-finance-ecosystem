import os
from datetime import datetime

import pandas as pd
from fredapi import Fred
from loguru import logger

from ..schema import enforce_schema

class FredFetcher:
    """
    FRED (Federal Reserve Economic Data) からマクロ指標を取得するフェッチャー。
    """
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("FRED_API_KEY")
        if not self.api_key:
            logger.warning("FRED_API_KEY is not set. Fetching might fail.")
        self.fred = Fred(api_key=self.api_key) if self.api_key else None

    @property
    def source_name(self) -> str:
        return "fred"

    def fetch(self, symbol: str, start_date: datetime) -> pd.DataFrame:
        """
        指定された指標をFREDから取得する。
        """
        if not self.fred:
            logger.error("FRED API client not initialized. Check your API key.")
            return pd.DataFrame()

        logger.info(f"Fetching {symbol} from FRED starting from {start_date.date()}...")
        try:
            # Seriesが返ってくる
            series = self.fred.get_series(
                symbol,
                observation_start=start_date.strftime("%Y-%m-%d")
            )

            if series.empty:
                logger.warning(f"FRED returned no data for {symbol}")
                return pd.DataFrame()

            return enforce_schema(series, symbol, self.source_name)
        except Exception as e:
            logger.error(f"FRED error during fetch for {symbol}: {e}")
            return pd.DataFrame()
