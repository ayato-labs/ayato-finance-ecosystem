import functools
import json
import sys
import time
from pathlib import Path

from loguru import logger

from src.core.config import settings
from src.core.db import db_manager

# --- Logging Configuration ---
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Clear existing handlers to avoid duplicates
logger.remove()

# 1. Console Handler (Pretty printed for humans)
CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)
logger.add(sys.stderr, format=CONSOLE_FORMAT, level="INFO")

# 2. JSON File Handler (Structured for traceability)
# Retention: Keep last 2 files. 
# Rotation: New file per execution (simulated via 10MB or manual start)
logger.add(
    LOG_DIR / "execution.jsonl",
    format="{message}",
    serialize=True,
    level="DEBUG",
    rotation="10 MB",
    retention=2,
    encoding="utf-8"
)


# 3. Error Isolation Handler (Only errors, kept indefinitely for audit)
logger.add(
    LOG_DIR / "error.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
    level="ERROR",
    backtrace=True,
    diagnose=True,
    encoding="utf-8",
)


def trace_step(step_name=None):
    """
    Decorator for tracing latency, inputs, and outputs,
    and persisting them as structured logs and metrics.
    """

    def decorator(func):
        _step_name = step_name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            # Try to extract session_id and ticker for context
            session_id = kwargs.get("session_id", None)
            ticker = kwargs.get("ticker", None)

            # Simple heuristic to extract from positional args for USEngine methods
            if not session_id:
                for arg in args:
                    if isinstance(arg, str) and (
                        arg.startswith("edgar-sync") or arg.startswith("test-sync")
                    ):
                        session_id = arg
                        break

            if not ticker:
                for arg in args:
                    if isinstance(arg, str) and arg.isupper() and 1 <= len(arg) <= 5:
                        ticker = arg
                        break

            # Filter out 'self' and non-serializable args for inputs dump
            safe_args = []
            for arg in args[1:]:
                if isinstance(arg, list):
                    safe_args.append(f"<List: {len(arg)} items>")
                elif isinstance(arg, dict):
                    safe_args.append(f"<Dict: {len(arg)} keys>")
                elif hasattr(arg, "__dict__"):
                    safe_args.append(f"<{arg.__class__.__name__}>")
                else:
                    safe_args.append(str(arg))

            safe_kwargs = {}
            for k, v in kwargs.items():
                if isinstance(v, list):
                    safe_kwargs[k] = f"<List: {len(v)} items>"
                elif isinstance(v, dict):
                    safe_kwargs[k] = f"<Dict: {len(v)} keys>"
                elif hasattr(v, "__dict__"):
                    safe_kwargs[k] = f"<{v.__class__.__name__}>"
                else:
                    safe_kwargs[k] = str(v)

            inputs_str = json.dumps({"args": safe_args, "kwargs": safe_kwargs}, default=str)

            ctx_logger = logger.bind(run_id=session_id, ticker=ticker, step=_step_name)
            ctx_logger.info(f"[{_step_name}] Started. Inputs: {inputs_str}")

            status = "success"
            error_log = None
            outputs_str = None

            try:
                result = func(*args, **kwargs)
                # Keep output logging lightweight (do not dump giant dataframes)
                outputs_str = json.dumps({"result": "success"}, default=str)
                return result
            except Exception as e:
                status = "failed"
                error_log = str(e)
                ctx_logger.error(f"[{_step_name}] Failed: {error_log}")
                raise
            finally:
                latency_ms = (time.perf_counter() - start_time) * 1000
                ctx_logger.info(f"[{_step_name}] Completed in {latency_ms:.2f}ms. Status: {status}")

                # Persist metric to db
                try:
                    with db_manager.connect(settings.DB_PATH) as conn:
                        conn.execute(
                            """
                            INSERT INTO metrics 
                            (run_id, step_name, ticker, latency_ms, status, error_log, inputs, outputs)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                            [
                                session_id,
                                _step_name,
                                ticker,
                                latency_ms,
                                status,
                                error_log,
                                inputs_str,
                                outputs_str,
                            ],
                        )
                except Exception as db_err:
                    logger.error(f"Failed to write telemetry for {_step_name}: {db_err}")

        return wrapper

    return decorator
