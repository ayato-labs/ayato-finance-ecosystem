import threading
import time
from contextlib import contextmanager
from pathlib import Path

import duckdb
from loguru import logger


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
                with DuckDBManager._local_lock:
                    try:
                        conn = duckdb.connect(db_path_str, read_only=read_only)
                        logger.debug(f"Connected to {db_path} (read_only={read_only})")
                    except duckdb.ConnectionException:
                        logger.warning(
                            f"Connection mode mismatch for {db_path}. "
                            f"Falling back to Read-Write mode."
                        )
                        conn = duckdb.connect(db_path_str, read_only=False)
                break
            except (duckdb.IOException, OSError) as e:
                err_msg = str(e).lower()
                if any(kw in err_msg for kw in ["io error", "locked", "used by", "permission"]):
                    logger.debug(f"Database {db_path} is locked, retrying...")
                    time.sleep(1.0)
                else:
                    logger.error(f"Unexpected IO error connecting to {db_path}: {e}")
                    raise e
            except Exception as e:
                logger.exception(f"Critical error connecting to {db_path}: {e}")
                raise e

        if conn is None:
            logger.error(f"Failed to acquire database lock for {db_path} after {timeout_seconds}s.")
            raise duckdb.IOException(
                f"Failed to acquire database lock for {db_path} after {timeout_seconds}s."
            )

        try:
            yield conn
        finally:
            if conn:
                conn.close()


db_manager = DuckDBManager()
