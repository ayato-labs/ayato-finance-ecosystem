import sys
from pathlib import Path
from loguru import logger

# Project root logs directory
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Remove default handler
logger.remove()

# 1. Console Handler (Standard Output) - For developers to see real-time status
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    backtrace=True,
    diagnose=True,
)

# 2. Sequential Log Files - Retain exactly last 2 runs using rotation and retention
# Loguru's rotation="2" means it rotates after the log file has been created twice? 
# Actually, rotation="00:00" or size based is common. 
# To retain exactly 2 runs, we can use a simpler approach or rotation with retention.
logger.add(
    LOG_DIR / "app.log",
    rotation="10 MB", # Rotate when size reaches 10MB
    retention=2,      # Keep only last 2 files
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    serialize=True,   # Structured JSON logging
    level="DEBUG",
)

# 3. Isolated Error Logs - "Isolation Storage" for errors
logger.add(
    LOG_DIR / "error.log",
    level="ERROR",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    serialize=True,   # Structured JSON logging
    backtrace=True,
    diagnose=True,
)

def get_logger():
    return logger
