import ctypes
import os
import platform
import threading
import time
from contextlib import contextmanager

import duckdb

from src.shared.infra.config import settings
from src.shared.infra.logging_config import logger


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
        logger.warning(f"Failed to detect system RAM: {e}. Defaulting to 1GB.", exc_info=True)
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

    def _setup_connection_params(self, conn):
        """Sets memory limits and temp directory."""
        total_ram = get_system_ram_bytes()
        limit_bytes = int(total_ram * settings.MEM_LIMIT_RATIO)
        limit_gb = limit_bytes / (1024**3)

        conn.execute(f"SET memory_limit = '{limit_bytes}B'")
        conn.execute(f"SET temp_directory = '{settings.DATA_DIR}/tmp'")
        logger.debug(f"DuckDB memory limit set to {limit_gb:.2f} GB ({settings.MEM_LIMIT_RATIO}%)")

    def _attach_databases(self, conn, read_only: bool):
        """Attaches registry, facts, and narrative databases."""

        def get_attach_sql(path, name, ro):
            ro_flag = " (READ_ONLY)" if ro and str(path) != ":memory:" else ""
            return f"ATTACH IF NOT EXISTS '{path}' AS {name}{ro_flag}"

        conn.execute(get_attach_sql(settings.REGISTRY_DB_PATH, "registry_db", read_only))
        conn.execute(get_attach_sql(settings.FACTS_DB_PATH, "facts_db", read_only))
        conn.execute(get_attach_sql(settings.NARRATIVE_DB_PATH, "narr_db", read_only))

    @staticmethod
    @contextmanager
    def connect_master(read_only: bool = False, timeout_seconds: int = 60):
        """
        Connects to MASTER DB and ATTACHes all other databases.
        This is the SSoT (Single Source of Truth) entry point.
        """
        master_path = str(settings.MASTER_DB_PATH)
        is_memory = master_path == ":memory:"
        start_time = time.time()
        conn = None
        manager = DuckDBManager()

        while time.time() - start_time < timeout_seconds:
            try:
                with manager._local_lock:
                    if is_memory:
                        if manager._memory_conn is None:
                            manager._memory_conn = duckdb.connect(":memory:")
                            manager._attach_databases(manager._memory_conn, read_only)
                        conn = manager._memory_conn
                        yield conn
                        return
                    else:
                        conn = duckdb.connect(master_path, read_only=read_only)
                        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
                        manager._setup_connection_params(conn)
                        manager._attach_databases(conn, read_only)
                break
            except (duckdb.IOException, duckdb.ConnectionException, OSError) as e:
                logger.warning(f"DB Contention at {master_path}: {e}. Retrying...")
                time.sleep(1.0)
            except Exception as e:
                logger.error(f"Unexpected database error: {e}", exc_info=True)
                raise

        if conn is None:
            raise duckdb.IOException(f"Failed to acquire DB locks for {master_path}")

        try:
            yield conn
        finally:
            if conn and not is_memory:
                conn.close()


db_manager = DuckDBManager()
