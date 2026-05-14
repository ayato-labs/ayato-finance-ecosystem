import contextvars
import functools
import time
import uuid

from loguru import logger







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
