import threading
import time
from contextlib import contextmanager
from pathlib import Path
import duckdb
from loguru import logger
from src.core.config import settings

class DuckDBManager:
    _local_lock = threading.Lock()

    @staticmethod
    @contextmanager
    def connect(db_path: str | Path, read_only: bool = False, timeout_seconds: int = 30):
        db_path_str = str(db_path)
        start_time = time.time()
        conn = None
        while time.time() - start_time < timeout_seconds:
            try:
                with DuckDBManager._local_lock:
                    try:
                        conn = duckdb.connect(db_path_str, read_only=read_only)
                    except duckdb.ConnectionException as ce:
                        logger.debug(f"Read-only connection failed, attempting read-write for {db_path_str}: {ce}")
                        conn = duckdb.connect(db_path_str, read_only=False)
                        
                    # Apply basic PRAGMAs for performance bounds
                    conn.execute(f"PRAGMA memory_limit='{settings.DUCKDB_MEMORY_LIMIT}'")
                    conn.execute(f"PRAGMA threads={settings.DUCKDB_THREADS}")
                break
            except (duckdb.IOException, OSError) as e:
                logger.warning(f"Database {db_path_str} is locked, retrying in 1s... (Error: {e})")
                time.sleep(1.0)
        
        if conn is None:
            logger.error(f"Failed to acquire database lock for {db_path_str} after {timeout_seconds}s")
            raise duckdb.IOException(f"Failed to acquire lock for {db_path}")

        try:
            yield conn
        finally:
            if conn:
                conn.close()

db_manager = DuckDBManager()
