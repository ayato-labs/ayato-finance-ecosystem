import duckdb
import time
from contextlib import contextmanager
from pathlib import Path
from loguru import logger
import threading

class DuckDBManager:
    """
    Manages DuckDB connections with a focus on handling file locks and 
    serializing access across threads within the same process.
    """
    _local_lock = threading.Lock()

    @staticmethod
    @contextmanager
    def connect(db_path: str | Path, read_only: bool = False, timeout_seconds: int = 30):
        """
        Provides a context-managed DuckDB connection with retry logic for IO Errors (file locks).
        """
        db_path_str = str(db_path)
        start_time = time.time()
        conn = None
        
        while time.time() - start_time < timeout_seconds:
            try:
                # Use a global lock to prevent multiple threads in the same process 
                # from trying to open the file simultaneously if not necessary.
                with DuckDBManager._local_lock:
                    conn = duckdb.connect(db_path_str, read_only=read_only)
                break
            except (duckdb.IOException, OSError) as e:
                err_msg = str(e).lower()
                if any(kw in err_msg for kw in ["io error", "locked", "used by", "permission"]):
                    elapsed = int(time.time() - start_time)
                    logger.warning(
                        f"Database {db_path} is currently locked. "
                        f"Retrying in 1s... ({elapsed}s elapsed)"
                    )
                    time.sleep(1.0)
                else:
                    # Not a lock error, re-raise immediately
                    raise e

        if conn is None:
            raise duckdb.IOException(
                f"Failed to acquire database lock for {db_path} after {timeout_seconds}s."
            )

        try:
            yield conn
        finally:
            if conn:
                conn.close()

db_manager = DuckDBManager()
