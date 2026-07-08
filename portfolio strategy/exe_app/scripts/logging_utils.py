import os
import sys

from loguru import logger


def setup_logging(log_dir="logs", service_name="portfolio_rebalancer"):
    """
    Setup Loguru with JSON structured logging, rotation (keep last 2),
    and isolated error logging.
    """
    os.makedirs(log_dir, exist_ok=True)

    # Clear default handler
    logger.remove()

    # 1. Console Handler (Pretty printed for development)
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    logger.add(sys.stderr, format=log_format, level="INFO")
    # 2. Main Log File (Structured JSON, Rotated, Keep last 2)
    # rotation="00:00" or just using a startup rotation if we want "per execution"
    # To truly keep "last 2 executions", we can rotate at start.
    main_log = os.path.join(log_dir, f"{service_name}.jsonl")
    logger.add(
        main_log,
        format="{time} | {level} | {name}:{function}:{line} | {message}",
        serialize=True,  # JSON output
        rotation="10 MB",  # Size based rotation
        retention=2,  # Keep only the last 2 log files
        level="DEBUG",
    )

    # 3. Error Log File (Isolated, Only ERROR and above, 'error.log')
    error_log = os.path.join(log_dir, "error.log")
    logger.add(
        error_log,
        format="{time} | {level} | {name}:{function}:{line} | {message}",
        serialize=True,
        level="ERROR",
        backtrace=True,
        diagnose=True,
        filter=lambda record: record["level"].name == "ERROR",
    )

    return logger


if __name__ == "__main__":
    # Test logging setup
    log = setup_logging()
    log.debug("Debug message")
    log.info("Info message")
    try:
        raise ValueError("Intentional Error for testing isolated logging")
    except Exception as e:
        log.error(f"Captured Error: {e}")
