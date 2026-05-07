import os
import queue
from concurrent.futures import ThreadPoolExecutor

from fredapi import Fred
from loguru import logger


class FredCollector:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("FRED_API_KEY")
        if not self.api_key:
            logger.error("FRED_API_KEY not found in environment variables.")
            raise ValueError("FRED_API_KEY must be provided.")

        try:
            self.fred = Fred(api_key=self.api_key)
            # Validate API key immediately by making a lightweight call
            self.fred.get_series_info("DFF")
            logger.debug("FredCollector initialized and API key validated.")
        except Exception as e:
            logger.exception("Failed to initialize Fred API client or invalid API key.")
            raise


        self.data_queue = queue.Queue()

    def discover_series_by_category(self, category_id: int):
        """指定されたカテゴリー内のシリーズIDを探索する"""
        try:
            logger.info(f"Discovering series in category ID: {category_id}")
            series_list = self.fred.search_by_category(category_id)
            if series_list is None or series_list.empty:
                logger.warning(f"No series found in category {category_id}.")
                return []

            ids = series_list["id"].tolist()
            logger.info(f"Discovered {len(ids)} series in category {category_id}.")
            return ids
        except Exception:
            logger.exception(f"Error discovering series in category {category_id}")
            raise

    def fetch_series(self, symbol: str, start_date: str):
        """特定のシンボルのデータとメタデータを取得し、キューに投入する"""
        logger.debug(f"Starting fetch for {symbol} from {start_date}")
        try:
            # メタデータの取得
            logger.debug(f"Fetching metadata for {symbol}")
            meta = self.fred.get_series_info(symbol)
            self.data_queue.put(("metadata", meta))

            # 観測データの取得
            logger.debug(f"Fetching observations for {symbol}")
            series = self.fred.get_series(symbol, observation_start=start_date)

            if series is None or series.empty:
                logger.warning(f"No observations found for {symbol} since {start_date}")
                return

            df = series.to_frame(name="value")
            df["series_id"] = symbol
            df["date"] = df.index

            self.data_queue.put(("observations", df))
            logger.info(f"Successfully fetched and queued {symbol}")

        except Exception:
            logger.exception(f"Failed to fetch data for {symbol}")
            # エラーを握りつぶさず、必要に応じて再試行や上位への通知を検討
            # ここではログを詳細に残した上で、キューの停止を防ぐため継続

    def run(self, symbols: list[str], start_date: str):
        """複数シンボルの並列取得実行"""
        logger.info(f"Starting batch fetch for {len(symbols)} symbols.")
        try:
            with ThreadPoolExecutor(max_workers=5) as executor:
                for symbol in symbols:
                    executor.submit(self.fetch_series, symbol, start_date)

            # 完了を示すセンチネル
            self.data_queue.put(None)
            logger.info("Batch fetch submitted to executor.")
        except Exception:
            logger.exception("Critical error in Collector.run loop")
            self.data_queue.put(None)
            raise
