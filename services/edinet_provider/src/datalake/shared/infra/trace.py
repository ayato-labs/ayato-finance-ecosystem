import time
import json
import uuid
import contextvars
import functools
from functools import wraps
from loguru import logger


def init_logging():
    """
    Initialize loguru sinks by delegating to setup_logging.
    """
    if getattr(init_logging, "done", False):
        return

    from src.datalake.shared.infra.logging_config import setup_logging

    setup_logging()

    init_logging.done = True


def trace_step(step_name: str):
    """
    Decorator to trace a execution step.
    Logs inputs, outputs, and elapsed time in JSON format.
    Expects 'run_id' in kwargs or generates a new one.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract or generate run_id
            run_id = kwargs.get("run_id")
            if not run_id:
                run_id = str(uuid.uuid4())
                kwargs["run_id"] = run_id

            start_time = time.perf_counter()

            # Log input (safely serialized)
            try:
                safe_args = [str(a) for a in args]
                safe_kwargs = {k: str(v) for k, v in kwargs.items() if k != "run_id"}

                logger.info(
                    json.dumps(
                        {
                            "run_id": run_id,
                            "step": step_name,
                            "event": "start",
                            "inputs": {"args": safe_args, "kwargs": safe_kwargs},
                        },
                        ensure_ascii=False,
                    )
                )
            except Exception as le:
                logger.warning(f"Failed to log inputs: {le}")

            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start_time

                # Log success
                logger.info(
                    json.dumps(
                        {
                            "run_id": run_id,
                            "step": step_name,
                            "event": "end",
                            "status": "success",
                            "elapsed_sec": round(elapsed, 4),
                            # We don't log the full output to avoid huge log lines,
                            # but we could log the type or length
                            "output_summary": str(type(result)),
                        },
                        ensure_ascii=False,
                    )
                )

                return result
            except Exception as e:
                elapsed = time.perf_counter() - start_time

                # Log error
                logger.error(
                    json.dumps(
                        {
                            "run_id": run_id,
                            "step": step_name,
                            "event": "end",
                            "status": "error",
                            "elapsed_sec": round(elapsed, 4),
                            "error_message": str(e),
                        },
                        ensure_ascii=False,
                    )
                )
                raise e

        return wrapper

    return decorator


# ContextVar to hold the current trace ID
current_trace_id = contextvars.ContextVar("trace_id", default="root")


def trace_execution(func):
    """
    Decorator to log execution time and context using a persistent TraceID.
    Leverages ContextVar for thread-safe propagation.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Generate TraceID if not present (root call) or inherit if already set
        existing_id = current_trace_id.get()
        trace_id = existing_id if existing_id != "root" else str(uuid.uuid4())

        token = current_trace_id.set(trace_id)
        func_name = func.__name__

        # Inject TraceID into logger context
        with logger.contextualize(trace_id=trace_id):
            logger.debug(
                "Entering {func} | Args: {args} | Kwargs: {kwargs}",
                func=func_name,
                args=args,
                kwargs=kwargs,
            )

            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration = time.perf_counter() - start_time

                logger.info(
                    "Exiting {func} | Duration: {duration:.4f}s", func=func_name, duration=duration
                )
                return result
            except Exception as e:
                duration = time.perf_counter() - start_time
                logger.error(
                    "Failed {func} | Duration: {duration:.4f}s | Error: {error}",
                    func=func_name,
                    duration=duration,
                    error=e,
                    exc_info=True,
                )
                raise
            finally:
                current_trace_id.reset(token)

    return wrapper


def with_context(func):
    """
    A wrapper for functions being passed to ThreadPoolExecutor to ensure
    ContextVars (like trace_id) are propagated to the worker thread.
    """
    ctx = contextvars.copy_context()

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return ctx.run(func, *args, **kwargs)

    return wrapper
