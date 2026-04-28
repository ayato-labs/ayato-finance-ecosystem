import asyncio
import random
import re
from functools import wraps
from loguru import logger

def parse_retry_delay(error: Exception) -> float | None:
    """
    Gemini APIのエラーメッセージからリトライ待機時間を抽出する
    """
    error_str = str(error)
    match = re.search(r"retry in ([\d.]+)s", error_str)
    if match:
        return float(match.group(1))

    try:
        if hasattr(error, "message") and isinstance(error.message, dict):
            details = error.message.get("error", {}).get("details", [])
            for detail in details:
                if detail.get("@type") == "type.googleapis.com/google.rpc.RetryInfo":
                    delay_str = detail.get("retryDelay", "0s")
                    return float(delay_str.rstrip("s"))
    except Exception:
        pass
    return None

def retry_on_ai_quota(max_retries: int = 5, initial_backoff: float = 2.0):
    """
    429 RESOURCE_EXHAUSTED エラー時に指数バックオフでリトライするデコレータ
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    e_str = str(e).upper()
                    if "429" in e_str or "RESOURCE_EXHAUSTED" in e_str:
                        wait_time = parse_retry_delay(e) or (initial_backoff * (2 ** attempt))
                        # ジッターを追加
                        wait_time += random.uniform(0, 1)
                        logger.warning(
                            f"Gemini Quota Exceeded (429). Attempt {attempt+1}/{max_retries}. "
                            f"Waiting {wait_time:.2f}s before retry..."
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    raise e
            raise last_error
        return wrapper
    return decorator

class AIRateLimiter:
    """
    Gemini APIの呼び出し間隔を制御する簡易レートリミッター
    """
    _last_call_time: float = 0.0
    _lock = asyncio.Lock()
    INTERVAL = 2.0 # 秒

    @classmethod
    async def throttle(cls):
        async with cls._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - cls._last_call_time
            if elapsed < cls.INTERVAL:
                wait_time = cls.INTERVAL - elapsed
                await asyncio.sleep(wait_time)
            cls._last_call_time = asyncio.get_event_loop().time()
