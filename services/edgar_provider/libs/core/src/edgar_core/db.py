import threading
import time
from contextlib import contextmanager
from pathlib import Path

import duckdb
from loguru import logger

from edgar_core.config import settings


class DuckDBManager:
    _local_lock = threading.Lock()

    @staticmethod
    @contextmanager
    def connect(db_path: str | Path, read_only: bool = False, timeout_seconds: int = 30):
        db_path_str = str(db_path)

        # Enforce read-only if explicitly requested OR if we are in API mode
        effective_read_only = read_only or settings.EDGAR_COMPONENT == "api"

        start_time = time.time()
        conn = None
        while time.time() - start_time < timeout_seconds:
            try:
                with DuckDBManager._local_lock:
                    try:
                        conn = duckdb.connect(db_path_str, read_only=effective_read_only)
                    except duckdb.ConnectionException as ce:
                        # If we wanted read-only and it failed, we don't retry as read-write
                        # unless it was a transient error.
                        if effective_read_only:
                            logger.error(f"Failed to open DB in read-only mode: {ce}")
                            raise

                        logger.debug(
                            "Read-only connection failed, attempting read-write "
                            f"for {db_path_str}: {ce}"
                        )
                        conn = duckdb.connect(db_path_str, read_only=False)

                    # Apply basic PRAGMAs for performance bounds
                    conn.execute(f"PRAGMA memory_limit='{settings.db_memory_limit}'")
                    conn.execute(f"PRAGMA threads={settings.db_threads}")

                    # Set a dedicated temp directory for disk spilling
                    temp_dir = settings.DATA_DIR / "temp"
                    temp_dir.mkdir(exist_ok=True)
                    conn.execute(f"SET temp_directory='{str(temp_dir)}';")

                    # Disable insertion order preservation to drastically save memory
                    # during bulk loads
                    conn.execute("SET preserve_insertion_order=false;")
                break
            except (duckdb.IOException, OSError) as e:
                logger.warning(f"Database {db_path_str} is locked, retrying in 1s... (Error: {e})")
                time.sleep(1.0)

        if conn is None:
            logger.error(
                f"Failed to acquire database lock for {db_path_str} after {timeout_seconds}s"
            )
            raise duckdb.IOException(f"Failed to acquire lock for {db_path}")

        try:
            yield conn
        finally:
            if conn:
                conn.close()


db_manager = DuckDBManager()
