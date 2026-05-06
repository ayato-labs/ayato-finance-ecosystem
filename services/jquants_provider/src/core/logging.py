import functools
import sys
import time
from pathlib import Path

from loguru import logger


def setup_logging():
    """
    Configures Loguru for structured JSON logging with 2-run retention and error isolation.
    """
    logger.remove()

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    app_log = log_dir / "app.json.log"
    error_log = log_dir / "error.log"

    # Execution-based rotation (Keep last 2 runs)
    # Move current to .1, previous .1 is deleted.
    try:
        if app_log.exists():
            backup_log = log_dir / "app.json.log.1"
            if backup_log.exists():
                backup_log.unlink()
            app_log.rename(backup_log)

        if error_log.exists():
            backup_err = log_dir / "error.log.1"
            if backup_err.exists():
                backup_err.unlink()
            error_log.rename(backup_err)
    except PermissionError:
        # On Windows, if the file is in use, we skip rotation rather than crashing.
        pass
    except Exception as e:
        print(f"Warning: Failed to rotate logs: {e}", file=sys.stderr)

    # 1. Main JSON Log (All INFO and above)
    logger.add(
        str(app_log),
        serialize=True,
        level="DEBUG",
        backtrace=True,
        diagnose=True,
    )

    # 2. Isolated Error Log (Human readable for quick debugging, ERROR and above)
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

    logger.debug("Logging initialized: JSON structured file and error isolation active.")


def track_performance(name: str):
    """Decorator to track performance and ensure exceptions are never silenced."""

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
                    f"FAILED {name}: {type(e).__name__} - {str(e)}",
                    extra={
                        "context": context,
                        "error": type(e).__name__,
                        "event": "failure",
                    },
                )
                # NEVER silence: re-raise the exception
                raise

        return wrapper

    return decorator


