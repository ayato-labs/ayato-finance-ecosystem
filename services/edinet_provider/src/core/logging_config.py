import sys
import os
from pathlib import Path
from loguru import logger

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logger.remove()

# Console output for visibility during development
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>",
    level="INFO",
)

if os.getenv("TESTING") != "true":
    # 1. Main JSON log: rotate to keep only last 2 files
    logger.add(
        LOG_DIR / "app.log",
        rotation="100 MB",
        retention=2,
        serialize=True,
        level="DEBUG",
    )

    # 2. Isolated Error JSON log: Keep errors specifically
    logger.add(
        LOG_DIR / "error.log",
        level="ERROR",
        serialize=True,
        backtrace=True,
        diagnose=True,
    )

def get_logger():
    return logger
