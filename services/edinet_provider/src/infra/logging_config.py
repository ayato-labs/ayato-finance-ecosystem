import sys
from loguru import logger
from pathlib import Path
import json


def setup_logging():
    # Clear existing handlers
    logger.remove()

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Custom serializer to ensure standard JSON output
    def serializer(record):
        subset = {
            "timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "message": record["message"],
            "module": record["name"],
            "function": record["function"],
            "line": record["line"],
            "exception": None,
            "extra": record["extra"],
        }
        if record["exception"]:
            subset["exception"] = {
                "type": record["exception"].type.__name__,
                "value": str(record["exception"].value),
                "traceback": True,  # loguru handles the actual traceback formatting if needed
            }
        return json.dumps(subset)

    # 1. Console output (Colored & Human Readable)
    # We keep this for developer convenience in terminal.
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
    # Rotation="1 day" or similar can be added, but here we use run-based retention if possible via filename.
    # Actually, loguru's retention=2 works on the file set.
    app_log_path = log_dir / "app.log"
    logger.add(
        app_log_path,
        level="INFO",
        format="{message}",
        serialize=True,  # This uses loguru's internal JSON which is quite good
        rotation="10 MB",
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
