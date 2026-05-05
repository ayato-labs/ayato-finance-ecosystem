import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
import duckdb
from src.core.logging_config import get_logger

logger = get_logger()


class DuckDBManager:
    _local_lock = threading.Lock()
    _memory_conn = None

    @staticmethod
    @contextmanager
    def connect(db_path: str | Path, read_only: bool = False, timeout_seconds: int = 60):
        """
        Thread-safe context manager for DuckDB connections with retry logic for file locks.
        """
        db_path_str = str(db_path)

        if db_path_str == ":memory:":
            with DuckDBManager._local_lock:
                if DuckDBManager._memory_conn is None:
                    logger.debug("Initializing in-memory DuckDB connection.")
                    DuckDBManager._memory_conn = duckdb.connect(":memory:")
            yield DuckDBManager._memory_conn
            return

        start_time = time.time()
        conn = None

        logger.debug(f"Attempting to connect to database: {db_path_str} (PID: {os.getpid()})")

        while time.time() - start_time < timeout_seconds:
            try:
                # Local thread lock to prevent concurrent connect attempts in same process
                with DuckDBManager._local_lock:
                    conn = duckdb.connect(db_path_str, read_only=read_only)
                break
            except (duckdb.IOException, duckdb.ConnectionException, OSError) as e:
                # Log as warning and retry if lock is held by another process
                elapsed = int(time.time() - start_time)
                logger.warning(
                    f"DB Lock Contention (PID {os.getpid()}): {e}. "
                    f"Retrying... ({elapsed}/{timeout_seconds}s)"
                )
                time.sleep(2.0)
            except Exception as e:
                # Unexpected errors should be logged with full trace
                logger.error(f"Unexpected error while connecting to DuckDB: {e}", exc_info=True)
                raise

        if conn is None:
            logger.error(
                f"❌ Database connection TIMEOUT after {timeout_seconds}s (PID {os.getpid()})",
                db_path=db_path_str,
            )
            raise duckdb.IOException(
                f"Failed to acquire lock for {db_path} within {timeout_seconds}s"
            )

        try:
            logger.debug(f"Connected to {db_path_str}")
            yield conn
        finally:
            if conn:
                try:
                    conn.close()
                    logger.debug(f"Database connection closed for {db_path_str}")
                except Exception as e:
                    logger.error(f"Error while closing DuckDB connection: {e}", exc_info=True)


db_manager = DuckDBManager()
