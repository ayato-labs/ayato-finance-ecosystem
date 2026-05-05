import sys
import os
from pathlib import Path
from loguru import logger

# Project root logs directory
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Remove default handler
logger.remove()

# 1. Console Handler - Always active
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    backtrace=True,
    diagnose=True,
)

# 2. File Handlers - Skip in testing to avoid PermissionError/Contention on Win32
if os.getenv("TESTING") != "true":
    # Sequential Log Files
    logger.add(
        LOG_DIR / "app.log",
        rotation="10 MB",
        retention=2,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        serialize=True,
        level="DEBUG",
    )

    # Isolated Error Logs
    logger.add(
        LOG_DIR / "error.log",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        serialize=True,
        backtrace=True,
        diagnose=True,
    )

def get_logger():
    return logger
