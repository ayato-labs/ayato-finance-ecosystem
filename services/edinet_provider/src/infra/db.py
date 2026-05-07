import threading
import time
import os
import platform
import ctypes
from contextlib import contextmanager
import duckdb
from src.infra.logging_config import logger
from src.infra.config import settings


def get_system_ram_bytes() -> int:
    """Gets total system RAM in bytes without external dependencies."""
    try:
        if platform.system() == "Windows":

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return stat.ullTotalPhys
        else:
            # POSIX / Linux
            return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except Exception as e:
        logger.warning(f"Failed to detect system RAM: {e}. Defaulting to 1GB.")
        return 1 * 1024 * 1024 * 1024


class DuckDBManager:
    _local_lock = threading.Lock()
    _memory_conn = None

    @staticmethod
    def _reset_memory_db():
        """Helper for testing to clear the global in-memory connection."""
        with DuckDBManager._local_lock:
            if DuckDBManager._memory_conn:
                DuckDBManager._memory_conn.close()
                DuckDBManager._memory_conn = None

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

        is_memory = master_path == ":memory:"

        start_time = time.time()
        conn = None
        current_pid = os.getpid()

        logger.debug(f"[PID:{current_pid}] Attempting to connect to master DB: {master_path}")
        while time.time() - start_time < timeout_seconds:
            try:
                with DuckDBManager._local_lock:
                    if is_memory:
                        # ... (existing memory logic)
                        if DuckDBManager._memory_conn is None:
                            DuckDBManager._memory_conn = duckdb.connect(":memory:")
                            DuckDBManager._memory_conn.execute("ATTACH ':memory:' AS registry_db")
                            DuckDBManager._memory_conn.execute("ATTACH ':memory:' AS facts_db")
                            DuckDBManager._memory_conn.execute("ATTACH ':memory:' AS narr_db")
                        conn = DuckDBManager._memory_conn
                        yield conn
                        return
                    else:
                        conn = duckdb.connect(master_path, read_only=read_only)
                        # ... (rest of disk logic)
                        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)

                        # Apply dynamic memory limit (Ratio of total RAM from settings)
                        total_ram = get_system_ram_bytes()
                        limit_bytes = int(total_ram * settings.MEM_LIMIT_RATIO)
                        limit_gb = limit_bytes / (1024**3)

                        conn.execute(f"SET memory_limit = '{limit_bytes}B'")
                        # Set temp directory for spilling to disk if memory limit is hit
                        conn.execute(f"SET temp_directory = '{settings.DATA_DIR}/tmp'")

                        logger.debug(
                            f"DuckDB memory limit set to {limit_gb:.2f} GB (30% of system RAM)"
                        )

                        def get_attach_sql(path, name, ro):
                            ro_flag = " (READ_ONLY)" if ro and path != ":memory:" else ""
                            return f"ATTACH IF NOT EXISTS '{path}' AS {name}{ro_flag}"

                        conn.execute(get_attach_sql(reg_path, "registry_db", read_only))
                        conn.execute(get_attach_sql(facts_path, "facts_db", read_only))
                        conn.execute(get_attach_sql(narr_path, "narr_db", read_only))

                break
            except (duckdb.IOException, duckdb.ConnectionException, OSError) as e:
                logger.warning(
                    f"[{current_pid}] DB Contention at {master_path}. "
                    f"Error: {e}. Retrying (Elapsed: {time.time() - start_time:.1f}s)..."
                )
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
