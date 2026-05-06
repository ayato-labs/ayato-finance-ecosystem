import time
import functools
from loguru import logger
import uuid

def trace_execution(func):
    """
    Decorator to log execution time, input context, and provide a unique trace ID
    for high-granularity traceability in development.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        trace_id = str(uuid.uuid4())
        func_name = func.__name__
        
        # Log entry context
        logger.debug(
            "Entering {func} | TraceID: {id} | Args: {args} | Kwargs: {kwargs}",
            func=func_name, id=trace_id, args=args, kwargs=kwargs
        )
        
        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            duration = time.perf_counter() - start_time
            
            # Log exit context with performance metrics
            logger.info(
                "Exiting {func} | TraceID: {id} | Duration: {duration:.4f}s",
                func=func_name, id=trace_id, duration=duration
            )
            return result
        except Exception as e:
            duration = time.perf_counter() - start_time
            logger.error(
                "Failed {func} | TraceID: {id} | Duration: {duration:.4f}s | Error: {error}",
                func=func_name, id=trace_id, duration=duration, error=e
            )
            raise
            
    return wrapper
