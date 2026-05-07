import time
from loguru import logger
from src.infra.config import settings
from src.infra.logging_config import setup_logging

def cleanup_raw_data(ttl_days: int = 30):
    """
    Deletes raw cached files older than `ttl_days` to prevent storage exhaustion.
    """
    setup_logging()
    
    if not settings.RAW_DATA_DIR.exists():
        logger.info("Raw data directory does not exist yet. Skipping cleanup.")
        return

    now = time.time()
    cutoff_time = now - (ttl_days * 86400)
    
    deleted_count = 0
    reclaimed_bytes = 0
    
    logger.info(f"Starting cleanup of raw data older than {ttl_days} days...")
    
    for file_path in settings.RAW_DATA_DIR.glob("*.zst"):
        try:
            # check modification time
            mtime = file_path.stat().st_mtime
            if mtime < cutoff_time:
                size = file_path.stat().st_size
                file_path.unlink()
                deleted_count += 1
                reclaimed_bytes += size
                logger.debug(f"Deleted old cache file: {file_path.name}")
        except Exception as e:
            logger.warning(f"Failed to process or delete {file_path}: {e}")

    logger.info(f"Cleanup completed. Deleted {deleted_count} files, reclaimed {reclaimed_bytes / (1024*1024):.2f} MB.")

if __name__ == "__main__":
    try:
        cleanup_raw_data()
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
