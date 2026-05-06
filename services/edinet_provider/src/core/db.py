import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
import duckdb
from src.core.logging_config import logger
from src.core.config import settings

class DuckDBManager:
    _local_lock = threading.Lock()
    _memory_conn = None

    @staticmethod
    @contextmanager
    def connect_master(read_only: bool = False, timeout_seconds: int = 60):
        """
        Connects to MASTER DB and ATTACHes all other databases.
        This is the SSoT (Single Source of Truth) entry point.
        """
        master_path = str(settings.MASTER_DB_PATH)
        reg_path = str(settings.REGISTRY_DB_PATH)
        facts_path = str(settings.FACTS_DB_PATH)
        narr_path = str(settings.NARRATIVE_DB_PATH)

        if master_path == ":memory:":
            with DuckDBManager._local_lock:
                if DuckDBManager._memory_conn is None:
                    logger.debug("Initializing in-memory database connection.")
                    DuckDBManager._memory_conn = duckdb.connect(":memory:")
            yield DuckDBManager._memory_conn
            return

        start_time = time.time()
        conn = None

        logger.debug(f"Attempting to connect to master DB: {master_path}")
        while time.time() - start_time < timeout_seconds:
            try:
                with DuckDBManager._local_lock:
                    conn = duckdb.connect(master_path, read_only=read_only)
                    
                    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
                    
                    # ATTACH the tiered architecture
                    logger.debug("Attaching sub-databases: registry, facts, narratives")
                    conn.execute(f"ATTACH IF NOT EXISTS '{reg_path}' AS registry_db")
                    conn.execute(f"ATTACH IF NOT EXISTS '{facts_path}' AS facts_db")
                    conn.execute(f"ATTACH IF NOT EXISTS '{narr_path}' AS narr_db")
                break
            except (duckdb.IOException, duckdb.ConnectionException, OSError) as e:
                logger.warning(f"Database contention at {master_path}: {e}. Retrying...")
                time.sleep(1.0)
            except Exception as e:
                logger.error(f"Unexpected database error: {e}", exc_info=True)
                raise

        if conn is None:
            err_msg = f"Failed to acquire DB locks for {master_path} within {timeout_seconds}s"
            logger.error(f"❌ {err_msg}")
            raise duckdb.IOException(err_msg)

        try:
            yield conn
        finally:
            if conn:
                logger.debug("Closing database connection.")
                conn.close()

db_manager = DuckDBManager()
