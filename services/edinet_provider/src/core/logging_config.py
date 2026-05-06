import sys
import json
from loguru import logger
from pathlib import Path

def setup_logging():
    # Clear existing handlers
    logger.remove()

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # 1. General log: JSON format, rotation to keep only 2 files
    logger.add(
        log_dir / "app.log",
        format="{message}",
        serialize=True,
        rotation="10 MB",
        retention=2,
        level="INFO"
    )

    # 2. Error log: JSON format, only ERROR level, rotation to keep 2 files
    logger.add(
        log_dir / "error.log",
        format="{message}",
        serialize=True,
        rotation="10 MB",
        retention=2,
        level="ERROR"
    )

    # 3. Console output for development
    logger.add(sys.stderr, level="DEBUG", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")

    logger.info("Logging configured with JSON structure and error isolation.")
