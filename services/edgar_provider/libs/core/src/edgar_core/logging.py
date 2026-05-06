import functools
import json
import sys
import time
from pathlib import Path

from loguru import logger


def setup_logging():
    """
    Configures Loguru for structured JSON logging with 2-run retention and error isolation.
    """
    # Remove default handler
    logger.remove()

    # Find project root (data and logs should be at root)
    # We navigate up relative to this file
    project_root = Path(__file__).parent.parent.parent.parent.parent
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)

    app_log = log_dir / "app.json.log"
    error_log = log_dir / "error.log"

    # Execution-based rotation (Keep last 2 runs)
    try:
        if app_log.exists():
            backup_log = log_dir / "app.json.log.1"
            if backup_log.exists():
                backup_log.unlink()
            app_log.rename(backup_log)

        # For the error log, we keep the previous run as well
        if error_log.exists():
            backup_err = log_dir / "error.log.1"
            if backup_err.exists():
                backup_err.unlink()
            error_log.rename(backup_err)
    except PermissionError:
        # On Windows, if file is locked, rotation might fail
        pass
    except Exception as e:
        print(f"Warning: Failed to rotate logs: {e}", file=sys.stderr)

    # Handler for JSON serialization
    def serialize_json(record):
        subset = {
            "timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "message": record["message"],
            "name": record["name"],
            "function": record["function"],
            "line": record["line"],
            "extra": record["extra"],
        }
        if record["exception"]:
            subset["exception"] = str(record["exception"])
        return json.dumps(subset)

    def json_sink(message):
        serialized = serialize_json(message.record)
        print(serialized, file=open(app_log, "a", encoding="utf-8"))

    # 1. Main JSON Log (Full traceability)
    logger.add(
        json_sink,
        level="DEBUG",
        backtrace=True,
        diagnose=True,
    )

    # 2. Isolated Error Log (Human readable, separate preservation)
    logger.add(
        str(error_log),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        backtrace=True,
        diagnose=True,
    )

    # 3. Console (Human readable)
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<level>{message}</level>",
        level="INFO",
        colorize=True,
    )

    logger.debug("Logging initialized with JSON and Error isolation.")


def track_performance(name: str):
    """Decorator to track performance and ensure exceptions are logged before re-raising."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            context = {"function": func.__name__, "step": name}
            logger.debug(f"Starting {name}", extra={"context": context, "event": "start"})
            start = time.perf_counter()

            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                logger.info(
                    f"Completed {name} in {elapsed:.4f}s",
                    extra={
                        "context": context,
                        "metrics": {"elapsed": round(elapsed, 4)},
                        "event": "end",
                    },
                )
                return result
            except Exception as e:
                logger.error(
                    f"CRITICAL FAILURE in {name}: {type(e).__name__} - {str(e)}",
                    extra={
                        "context": context,
                        "error_type": type(e).__name__,
                        "event": "failure",
                    },
                )
                # Ensure the error is never silenced
                raise

        return wrapper

    return decorator
