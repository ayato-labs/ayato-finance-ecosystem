import sys
from loguru import logger
import functools
import time
from pathlib import Path


def setup_logging():
    """
    Configure loguru logging with structured JSON, execution-based rotation, and error isolation.

    Retention: Keeps the last 2 executions.
    Error Isolation: Captures ERROR and CRITICAL events into a separate error.log.
    Format: JSON for machine readability.
    """
    logger.remove()

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    app_log = log_dir / "app.log"
    error_log = log_dir / "error.log"

    # Execution-based manual rotation (Keep last 2)
    if app_log.exists():
        old_log = log_dir / "app.log.1"
        if old_log.exists():
            old_log.unlink()
        app_log.rename(old_log)

    if error_log.exists():
        old_err = log_dir / "error.log.1"
        if old_err.exists():
            old_err.unlink()
        error_log.rename(old_err)

    # Standard Execution Log (JSON)
    logger.add(
        str(app_log),
        serialize=True,
        level="INFO",
        backtrace=True,
        diagnose=True,
    )

    # Isolated Error Log (Strictly for ERROR level)
    logger.add(
        str(error_log),
        serialize=True,
        level="ERROR",
        backtrace=True,
        diagnose=True,
    )

    # Console Output (Standard Output for better CLI piping)
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<level>{message}</level>",
        level="INFO",
        colorize=True
    )



def track_performance(name: str):
    """Decorator to track performance with structured JSON logs."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            context = {"function": func.__name__, "step": name}
            logger.info(f"Starting {name}", extra={"context": context, "event": "start"})
            start = time.perf_counter()

            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                logger.info(
                    f"Completed {name}",
                    extra={
                        "context": context,
                        "metrics": {"elapsed": round(elapsed, 4)},
                        "event": "end",
                    },
                )
                return result
            except Exception as e:
                logger.error(
                    f"Failed {name}",
                    extra={
                        "context": context,
                        "error": type(e).__name__,
                        "message": str(e),
                        "event": "failure",
                    },
                )
                raise

        return wrapper

    return decorator
