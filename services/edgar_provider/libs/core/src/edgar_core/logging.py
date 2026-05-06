import json
import sys
import time
from pathlib import Path

from loguru import logger


def patch_record(record):
    """
    Patches the log record with traceability context from ContextVars.
    Done lazily to avoid circular imports.
    """
    try:
        from edgar_core.telemetry import run_id_var, step_var, ticker_var

        record["extra"]["run_id"] = run_id_var.get()
        record["extra"]["ticker"] = ticker_var.get()
        record["extra"]["step"] = step_var.get()
    except ImportError:
        pass


def setup_logging():
    """
    Configures Loguru for structured JSON logging with 2-run retention and error isolation.
    """
    # Remove default handler
    logger.remove()

    # Apply traceability patcher
    logger.configure(patcher=patch_record)

    # Find project root
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

        if error_log.exists():
            backup_err = log_dir / "error.log.1"
            if backup_err.exists():
                backup_err.unlink()
            error_log.rename(backup_err)
    except PermissionError:
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
            "run_id": record["extra"].get("run_id"),
            "ticker": record["extra"].get("ticker"),
            "step": record["extra"].get("step"),
            "extra": {k: v for k, v in record["extra"].items() if k not in ["run_id", "ticker", "step"]},
        }
        if record["exception"]:
            subset["exception"] = str(record["exception"])
        return json.dumps(subset)

    def json_sink(message):
        serialized = serialize_json(message.record)
        with open(app_log, "a", encoding="utf-8") as f:
            f.write(serialized + "\n")

    # 1. Main JSON Log (Full traceability)
    logger.add(
        json_sink,
        level="DEBUG",
        backtrace=True,
        diagnose=True,
    )

    # 2. Isolated Error Log (Human readable)
    logger.add(
        str(error_log),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | "
               "run_id={extra[run_id]} step={extra[step]} - {message}",
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

    logger.debug("Logging initialized with JSON, Error isolation, and Traceability.")
