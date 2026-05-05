import threading
import time
from contextlib import contextmanager
from pathlib import Path
import duckdb
from src.core.logging_config import get_logger

logger = get_logger()

class DuckDBManager:
    _local_lock = threading.Lock()

    @staticmethod
    @contextmanager
    def connect(db_path: str | Path, read_only: bool = False, timeout_seconds: int = 30):
        db_path_str = str(db_path)
        start_time = time.time()
        conn = None
        
        logger.info("Attempting to connect to database", db_path=db_path_str)
        
        while time.time() - start_time < timeout_seconds:
            try:
                with DuckDBManager._local_lock:
                    try:
                        conn = duckdb.connect(db_path_str, read_only=read_only)
                    except duckdb.ConnectionException:
                        logger.warning("ConnectionException, trying read_only=False")
                        conn = duckdb.connect(db_path_str, read_only=False)
                break
            except (duckdb.IOException, OSError) as e:
                logger.error("Failed to connect to database", error=str(e))
                time.sleep(1.0)
        
        if conn is None:
            logger.error("Connection failed after timeout", db_path=db_path_str)
            raise duckdb.IOException(f"Failed to acquire lock for {db_path}")

        try:
            yield conn
        finally:
            if conn:
                conn.close()
                logger.info("Database connection closed", db_path=db_path_str)

db_manager = DuckDBManager()
