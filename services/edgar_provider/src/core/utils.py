import threading
import time
from pathlib import Path

import requests
from loguru import logger

from src.core.config import settings


class RateLimiter:
    """
    A thread-safe rate limiter using a simple token bucket-like approach
    to ensure we don't exceed the SEC's limit of 10 requests/second.
    """

    def __init__(self, requests_per_second: float):
        self.delay = 1.0 / requests_per_second
        self.last_call = 0.0
        self.lock = threading.Lock()

    def wait(self):
        """Wait if necessary to maintain the rate limit."""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_call
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
            self.last_call = time.time()


# Global rate limiter set to 9 requests per second for safety
rate_limiter = RateLimiter(9.0)


def download_file(url: str, dest_path: Path):
    """Downloads a file with streaming to handle large bulk data."""
    headers = {"User-Agent": settings.SEC_IDENTITY}
    logger.info(f"Downloading {url} to {dest_path}...")

    try:
        with requests.get(url, headers=headers, stream=True) as r:
            r.raise_for_status()
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):  # 1MB chunks
                    f.write(chunk)
        logger.info(f"Successfully downloaded {url}")
        return True
    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
        return False


def get_all_tickers():
    """Fetches all company tickers from SEC EDGAR."""
    url = "https://www.sec.gov/files/company_tickers.json"
    headers = {"User-Agent": settings.SEC_IDENTITY}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        # Parse the data into a list of dictionaries
        tickers = []
        for key in data:
            item = data[key]
            tickers.append(
                {
                    "ticker": item["ticker"],
                    "cik": str(item["cik_str"]).zfill(10),
                    "title": item["title"],
                }
            )
        return tickers
    except Exception as e:
        logger.error(f"Failed to fetch tickers from SEC: {e}")
        return []
