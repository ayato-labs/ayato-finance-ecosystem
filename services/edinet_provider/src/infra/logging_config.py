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
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        enqueue=True
    )

    # 2. General app log (Structured JSON)
    # Uses timestamp to ensure each run is a new file, retention=2 keeps last two runs.
    logger.add(
        log_dir / "app_{time:YYYY-MM-DD_HH-mm-ss}.log",
        format="{message}",
        serialize=True,
        retention=2,
        level="INFO",
        enqueue=True
    )

    # 3. Dedicated Error Isolation (Structured JSON)
    # Always appends to error.log for historical tracking of failures.
    # Rotates at 10MB to prevent bloat, but error isolation is the priority.
    logger.add(
        log_dir / "error.log",
        format="{message}",
        serialize=True,
        rotation="10 MB",
        retention=5,
        level="ERROR",
        filter=lambda record: record["level"].name == "ERROR",
        enqueue=True
    )

    logger.info("Observability platform initialized with run-based rotation.")
