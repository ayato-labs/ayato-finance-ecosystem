import sys
from loguru import logger
from pathlib import Path


def setup_logging():
    # Clear existing handlers
    logger.remove()

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # 1. Console output (Colored & Human Readable)
    logger.add(
        sys.stderr,
        level="DEBUG",
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        enqueue=True,
    )

    # 2. General app log (Structured JSON)
    # Retention=2 keeps only the last 2 log files.
    app_log_format = "app.{time:YYYY-MM-DD_HH-mm-ss_SSSSSS}.log"
    logger.add(
        log_dir / app_log_format,
        level="INFO",
        serialize=True,
        retention=2,
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )

    # 3. Dedicated Error Isolation (Structured JSON)
    logger.add(
        log_dir / "error.log",
        level="ERROR",
        serialize=True,
        rotation="10 MB",
        retention=5,
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )

    logger.debug(
        "Logging initialized. App logs limited to last 2 runs. Errors isolated to error.log."
    )
