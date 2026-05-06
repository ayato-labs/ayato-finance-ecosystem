import sys
import os
from loguru import logger
from pathlib import Path

def setup_logging():
    """
    Configures structured JSON logging with:
    - Rotation: Retention of last 2 app log files.
    - Error Isolation: Separate error.log for ERROR+ level.
    - JSON Serialization: Required for machine-readable traceability.
    - Contextual Tracing: Supports trace_id propagation.
    """
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Clear default handlers
    logger.remove()

    # 1. Main JSON Log (All levels)
    logger.add(
        log_dir / "app.log",
        rotation="100 MB",
        retention=2,
        serialize=True,
        level="DEBUG"
    )

    # 2. Error Isolation Log (ERROR+ only)
    logger.add(
        log_dir / "error.log",
        level="ERROR",
        serialize=True,
        backtrace=True,
        diagnose=True
    )

    # 3. Console output for development (Text based for readability)
    # Using a filter to handle cases with and without trace_id
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
               "<cyan>{name}:{function}:{line}</cyan> | <magenta>{extra[trace_id]}</magenta> - <level>{message}</level>",
        level="INFO",
        filter=lambda record: "trace_id" in record["extra"]
    )
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
               "<cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>",
        level="INFO",
        filter=lambda record: "trace_id" not in record["extra"]
    )
