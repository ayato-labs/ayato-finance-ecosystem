import time
import os
from pathlib import Path
from loguru import logger
from src.core.config import settings

class RateLimiter:
    """
    A simple file-based rate limiter to coordinate across multiple processes.
    Ensures that J-Quants API calls stay within the requested rate limit.
    """
    def __init__(self, requests_per_minute: int = 5):
        # Even more conservative: 15s between requests (4 req/min)
        self.interval = 15.0
        
        self.lock_file = settings.DATA_DIR / ".api_rate_limit"
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)

    def wait(self):
        """Wait if necessary to stay within the rate limit."""
        while True:
            try:
                # Use a lock file to store the timestamp of the last request
                if not self.lock_file.exists():
                    self.lock_file.write_text(str(time.time()))
                    return

                # Read last request time
                try:
                    last_request_time = float(self.lock_file.read_text())
                except (ValueError, TypeError):
                    last_request_time = 0

                now = time.time()
                elapsed = now - last_request_time
                
                if elapsed < self.interval:
                    wait_time = self.interval - elapsed
                    logger.info(f"Rate limiting: Waiting {wait_time:.2f}s for J-Quants API quota...")
                    time.sleep(wait_time)
                    # Loop again to re-check (in case another process updated it)
                    continue
                
                # Update last request time
                # In a real multi-process environment, we might want a proper file lock here,
                # but for 5 req/min, a simple write is usually sufficient.
                self.lock_file.write_text(str(time.time()))
                break
            except Exception as e:
                logger.warning(f"Rate limiter error: {e}. Defaulting to 2s sleep.")
                time.sleep(2.0)
                break

# Global instance
rate_limiter = RateLimiter(requests_per_minute=settings.JQUANTS_RATE_LIMIT)

def rate_limit(func):
    """Decorator to apply rate limiting to a function."""
    def wrapper(*args, **kwargs):
        rate_limiter.wait()
        return func(*args, **kwargs)
    return wrapper
