import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
from fredapi import Fred
import os
import pandas as pd
from datetime import datetime

class FredCollector:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("FRED_API_KEY")
        self.fred = Fred(api_key=self.api_key) if self.api_key else None
        self.data_queue = queue.Queue()

    def fetch_series(self, symbol: str, start_date: str):
        try:
            logger.info(f"Fetching {symbol} from FRED", extra={"series_id": symbol})
            series = self.fred.get_series(symbol, observation_start=start_date)
            df = series.to_frame(name="value")
            df["series_id"] = symbol
            df["date"] = df.index
            self.data_queue.put(df)
            logger.debug(f"Successfully fetched {symbol}")
        except Exception as e:
            logger.error(f"Failed to fetch {symbol}: {e}", extra={"series_id": symbol, "error": str(e)})

    def run(self, symbols: list[str], start_date: str):
        with ThreadPoolExecutor(max_workers=5) as executor:
            for symbol in symbols:
                executor.submit(self.fetch_series, symbol, start_date)
        self.data_queue.put(None)  # Sentinel to signal completion
