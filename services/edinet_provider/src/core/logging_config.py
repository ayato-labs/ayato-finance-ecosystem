import sys
from loguru import logger
from pathlib import Path
from src.core.config import settings

def setup_logging():
    """
    Configures structured JSON logging with:
    - Rotation: Retention of last 2 app log files.
    - Error Isolation: Separate error.log for ERROR+ level.
    - JSON Serialization: Required for machine-readable traceability.
    """
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Clear default handlers
    logger.remove()

    # 1. Main JSON Log (All levels)
    logger.add(
        log_dir / "app.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        rotation="10 MB",
        retention=2,
        serialize=True,
        level="DEBUG"
    )

    # 2. Error Isolation Log (ERROR+ only)
    logger.add(
        log_dir / "error.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        rotation="10 MB",
        retention=5, # Retain a bit more for errors
        level="ERROR",
        serialize=True,
        backtrace=True,
        diagnose=True
    )

    # 3. Console output for development
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
