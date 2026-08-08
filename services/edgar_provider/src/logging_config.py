import os
import sys

from loguru import logger


def setup_logger(log_dir: str = "logs", app_name: str = "app"):
    """
    Configure Loguru to:
    1. Output JSON (structured) logs to a file.
    2. Keep only the last 2 runs (files).
    3. Isolate ERROR logs to 'error.log'.
    4. Provide detailed traceability for debugging.
    """
    os.makedirs(log_dir, exist_ok=True)

    # Clear existing handlers
    logger.remove()

    logger_configured = logger.bind(stage="main")

    # 1. Console handler (Human-friendly)
    logger_configured.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <yellow>[{extra[stage]}]</yellow> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

    # 2. Main structured log (JSONL)
    # To keep exactly 2 runs, we use a timestamped filename and retention=2.
    log_file_pattern = os.path.join(log_dir, f"{app_name}_{{time:YYYYMMDD_HHmmss}}.jsonl")
    logger.add(
        log_file_pattern,
        level="DEBUG",
        serialize=True,
        rotation="10 MB",
        retention=2,
        compression="zip",
        enqueue=True,
        backtrace=True,
        diagnose=True,
        encoding="utf-8",
    )

    # 3. Isolated Error Log (JSONL)
    error_log = os.path.join(log_dir, "error.log")
    logger.add(
        error_log,
        level="ERROR",
        serialize=True,
        rotation="10 MB",
        retention=5,
        enqueue=True,
        backtrace=True,
        diagnose=True,
        encoding="utf-8",
    )

    logger.debug(f"Logging initialized. App: {app_name}, Dir: {log_dir}")

    return logger
