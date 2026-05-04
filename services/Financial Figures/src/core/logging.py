import sys

from loguru import logger

from src.core.config import settings


def setup_logging():
    """
    Configures Loguru for structured JSON logging with the following features:
    1. Stderr output (Pretty format for development).
    2. JSON logging for traceability (app.json.log).
    3. Error isolation (error.log).
    4. Retention of the last 2 executions.
    """
    # Ensure logs directory exists
    log_dir = settings.PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)

    # Remove default handler
    logger.remove()

    # 1. Console Output (Human-readable)
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    logger.add(
        sys.stderr,
        format=console_format,
        level="INFO",
        colorize=True,
    )

    # 2. Structured JSON Log (Last 2 executions)
    # rotation=0 means "rotate on start"
    # retention=2 means "keep last 2 rotated files"
    logger.add(
        log_dir / "app.json.log",
        serialize=True,
        level="INFO",
        rotation=0,
        retention=2,
        encoding="utf-8",
    )

    # 3. Isolated Error Log (Continuous, only errors)
    # We want a separate file that strictly captures errors for quick debugging.
    # Note: Using a different name to avoid collision with retention policy of app.json.log
    logger.add(
        log_dir / "error.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        backtrace=True,
        diagnose=True,
        encoding="utf-8",
        # Keep errors for a bit longer or larger size, as they are "isolated storage"
        rotation="10 MB",
        retention=5,
    )

    logger.info("Logging system initialized (JSON + Error Isolation)")
