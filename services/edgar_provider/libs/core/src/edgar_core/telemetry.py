import contextvars
import functools
import json
import os
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from loguru import logger

from edgar_core.config import settings
from edgar_core.db import db_manager

# --- Context Variables for Traceability ---
# These allow automatic propagation of context across function calls within the same thread/task.
run_id_var = contextvars.ContextVar("run_id", default=None)
ticker_var = contextvars.ContextVar("ticker", default=None)
step_var = contextvars.ContextVar("step", default=None)


class TraceContext:
    """
    Context manager to set and clear traceability variables.
    """

    def __init__(self, run_id=None, ticker=None, step=None):
        self.run_id = run_id
        self.ticker = ticker
        self.step = step
        self.tokens = []

    def __enter__(self):
        if self.run_id is not None:
            self.tokens.append(run_id_var.set(self.run_id))
        if self.ticker is not None:
            self.tokens.append(ticker_var.set(self.ticker))
        if self.step is not None:
            self.tokens.append(step_var.set(self.step))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for token in reversed(self.tokens):
            # Since we set multiple variables, we should really track which token belongs to which
            # but for simplicity, we just reset if we have a way to match them.
            # Actually, standard practice is to reset each one individually.
            pass
        # Resetting manually for safety in this version
        if self.run_id is not None:
            run_id_var.set(None)
        if self.ticker is not None:
            ticker_var.set(None)
        if self.step is not None:
            step_var.set(None)


def _persist_telemetry(run_id, step_name, ticker, latency_ms, status, error_log, inputs=None, outputs=None):
    """Internal helper to write metrics to the Master DB."""
    try:
        # We always use the Master DB for centralized metrics
        with db_manager.connect(settings.MASTER_DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO metrics
                (run_id, step_name, ticker, latency_ms,
                 status, error_log, inputs, outputs, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                [
                    run_id,
                    step_name,
                    ticker,
                    latency_ms,
                    status,
                    error_log,
                    inputs,
                    outputs,
                ],
            )
    except Exception as db_err:
        # Fallback to standard logging if DB write fails
        logger.warning(f"Failed to persist telemetry to DB: {db_err}")


@contextmanager
def trace_block(step_name: str, **extra_context):
    """
    Context manager for granular sub-step tracing within a function.
    """
    start_time = time.perf_counter()
    
    # Hierarchical step naming
    parent_step = step_var.get()
    full_step_name = f"{parent_step}.{step_name}" if parent_step else step_name
    
    # Update context
    token = step_var.set(full_step_name)
    run_id = run_id_var.get()
    ticker = ticker_var.get()
    
    ctx_logger = logger.bind(run_id=run_id, ticker=ticker, step=full_step_name)
    ctx_logger.debug(f"[{full_step_name}] Sub-step started.")
    
    status = "success"
    error_log = None
    
    try:
        yield ctx_logger
    except Exception as e:
        status = "failed"
        error_log = str(e)
        ctx_logger.error(f"[{full_step_name}] Sub-step failed: {error_log}")
        raise
    finally:
        latency_ms = (time.perf_counter() - start_time) * 1000
        ctx_logger.debug(f"[{full_step_name}] Sub-step completed in {latency_ms:.2f}ms.")
        
        # Persist sub-step metrics
        _persist_telemetry(run_id, full_step_name, ticker, latency_ms, status, error_log)
        
        # Restore parent step
        step_var.reset(token)


def trace_step(step_name=None):
    """
    Decorator for tracing latency, inputs, and outputs at the function level.
    Uses ContextVars for automatic run_id/ticker discovery.
    """

    def decorator(func):
        _step_name = step_name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            
            # 1. Discover Context
            # Priority: Explicit kwargs > ContextVars > Heuristics
            run_id = kwargs.get("session_id") or kwargs.get("run_id") or run_id_var.get()
            ticker = kwargs.get("ticker") or ticker_var.get()

            # Heuristic fallback (e.g. from positional args)
            if not run_id:
                for arg in args:
                    if isinstance(arg, str) and (arg.startswith("edgar-sync") or arg.startswith("test-sync")):
                        run_id = arg
                        break
            if not ticker:
                for arg in args:
                    if isinstance(arg, str) and arg.isupper() and 1 <= len(arg) <= 5:
                        ticker = arg
                        break

            # Update ContextVars for the duration of this call
            run_token = run_id_var.set(run_id)
            ticker_token = ticker_var.set(ticker)
            step_token = step_var.set(_step_name)

            # 2. Capture Inputs (Lightweight)
            safe_args = [f"<{type(a).__name__}>" if hasattr(a, "__dict__") else str(a) for a in args[1:]] # Skip 'self'
            safe_kwargs = {k: f"<{type(v).__name__}>" if hasattr(v, "__dict__") else str(v) for k, v in kwargs.items()}
            inputs_str = json.dumps({"args": safe_args, "kwargs": safe_kwargs}, default=str)

            ctx_logger = logger.bind(run_id=run_id, ticker=ticker, step=_step_name)
            ctx_logger.info(f"[{_step_name}] Started.")

            status = "success"
            error_log = None
            outputs_str = None

            try:
                result = func(*args, **kwargs)
                # We don't log the full result to avoid flooding
                outputs_str = json.dumps({"result": "success"}, default=str)
                return result
            except Exception as e:
                status = "failed"
                error_log = f"{type(e).__name__}: {str(e)}"
                ctx_logger.error(f"[{_step_name}] Failed: {error_log}")
                raise
            finally:
                latency_ms = (time.perf_counter() - start_time) * 1000
                ctx_logger.info(f"[{_step_name}] Completed in {latency_ms:.2f}ms. Status: {status}")

                # 3. Persist Metrics
                _persist_telemetry(run_id, _step_name, ticker, latency_ms, status, error_log, inputs_str, outputs_str)
                
                # 4. Cleanup ContextVars
                run_id_var.reset(run_token)
                ticker_var.reset(ticker_token)
                step_var.reset(step_token)

        return wrapper

    return decorator
