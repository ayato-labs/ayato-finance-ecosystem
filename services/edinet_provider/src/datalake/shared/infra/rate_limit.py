import threading
import time
from loguru import logger

class RateLimitManager:
    """
    Coordinates rate limit (429) backoff and proactive spacing across multiple threads.
    Enforces virtual time spacing to allow lock-free sleeping outside the lock.
    """
    def __init__(self, requests_per_second: float = 1.5):
        self._min_interval = 1.0 / requests_per_second
        self._last_request_time = time.monotonic()
        self._backoff_until = 0.0
        self._lock = threading.Lock()

    def check_and_wait(self):
        """Checks if a backoff is in effect or spaces out calls, and waits if necessary."""
        # Safeguard with max 10 iterations to prevent infinite loop if time.sleep is mocked in tests
        for _ in range(10):
            wait_time = 0.0
            is_backoff = False
            with self._lock:
                now = time.monotonic()
                
                # 1. Handle global backoff if 429 was hit
                if now < self._backoff_until:
                    wait_time = self._backoff_until - now
                    is_backoff = True
                    logger.warning(f"Global backoff in effect. Thread waiting {wait_time:.1f}s outside lock...")
                else:
                    # 2. Proactive rate limit spacing (Virtual Time spacing)
                    target_time = max(self._last_request_time + self._min_interval, now)
                    if target_time > now:
                        wait_time = target_time - now
                    
                    # Lock-in the request slot
                    self._last_request_time = target_time
            
            if wait_time > 0.0:
                time.sleep(wait_time)
                # If we slept for normal spacing, we don't need to re-evaluate (slot is already reserved)
                if not is_backoff:
                    return
            else:
                return  # No sleep needed, proceed
                
        # Safeguard fallback to proceed anyway after 10 loops (should only hit if mocked)
        return

    def trigger_backoff(self, seconds: float = 60.0):
        """Triggers a global backoff for all threads."""
        with self._lock:
            new_backoff = time.monotonic() + seconds
            if new_backoff > self._backoff_until:
                self._backoff_until = new_backoff
                logger.error(f"RATE LIMIT HIT. Global backoff triggered for {seconds}s.")

# Global instance for EDINET
edinet_rate_limit = RateLimitManager()
