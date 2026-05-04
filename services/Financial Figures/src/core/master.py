import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb
from loguru import logger

from src.core.config import settings
from src.core.db import db_manager


class MasterManager:
    """
    Centralized controller for the Master Database.
    Responsible for shard registration, job tracking, and universe indexing.
    """

    def __init__(self, db_path: Path = settings.DB_PATH_MASTER):
        self.db_path = db_path

    def _ensure_master_initialized(self):
        """
        Ensures the master database itself is migrated to the latest version.
        This is a bootstrapping step.
        """
        from src.core.migrations import MigrationManager
        MigrationManager.apply_migrations(self.db_path, "master")

    def sync_shard_status(self, shard_key: str, physical_path: Path):
        """
        Queries a shard for its current version and updates the master registry.
        """
        self._ensure_master_initialized()
        
        if not physical_path.exists():
            logger.warning(f"Shard {shard_key} path does not exist: {physical_path}")
            return

        try:
            # 1. Get shard info from the shard itself
            current_version = "UNKNOWN"
            with db_manager.connect(physical_path, read_only=True) as conn:
                res = conn.execute(
                    "SELECT current_version FROM _schema_version ORDER BY applied_at DESC LIMIT 1"
                ).fetchone()
                if res:
                    current_version = res[0]

            # 2. Get file system info
            stat = physical_path.stat()
            file_size = stat.st_size
            last_modified = datetime.fromtimestamp(stat.st_mtime)

            # 3. Update master registry
            with db_manager.connect(self.db_path, read_only=False) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO shard_registry 
                    (shard_id, physical_path, current_schema_version, health_status, last_migration_at, file_size_bytes, last_modified_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        shard_key,
                        str(physical_path),
                        current_version,
                        "HEALTHY",
                        datetime.now(),
                        file_size,
                        last_modified,
                    ],
                )
            logger.info(f"Master registry updated for shard '{shard_key}'.")
        except Exception as e:
            logger.error(f"Failed to sync shard status for '{shard_key}': {e}")
            with db_manager.connect(self.db_path, read_only=False) as conn:
                conn.execute(
                    "UPDATE shard_registry SET health_status = ?, error_message = ? WHERE shard_id = ?",
                    ["ERROR", str(e), shard_key]
                )

    def start_job(self, job_name: str, affected_shards: List[str] = None) -> str:
        """
        Registers the start of a new background job.
        Returns a unique job_id.
        """
        self._ensure_master_initialized()
        job_id = str(uuid.uuid4())
        shards_str = ",".join(affected_shards) if affected_shards else ""
        
        with db_manager.connect(self.db_path, read_only=False) as conn:
            conn.execute(
                """
                INSERT INTO job_tracker (job_id, job_name, status, affected_shards)
                VALUES (?, ?, ?, ?)
                """,
                [job_id, job_name, "RUNNING", shards_str],
            )
        logger.info(f"Job '{job_name}' started (ID: {job_id})")
        return job_id

    def end_job(self, job_id: str, status: str = "COMPLETED", records_processed: int = 0, error_message: str = None, metadata: Dict[str, Any] = None):
        """
        Updates the status of a finished job.
        """
        self._ensure_master_initialized()
        metadata_json = json.dumps(metadata) if metadata else None
        
        with db_manager.connect(self.db_path, read_only=False) as conn:
            conn.execute(
                """
                UPDATE job_tracker 
                SET status = ?, ended_at = ?, records_processed = ?, error_message = ?, metadata = ?
                WHERE job_id = ?
                """,
                [status, datetime.now(), records_processed, error_message, metadata_json, job_id],
            )
        logger.info(f"Job ID {job_id} finished with status: {status}")


master_manager = MasterManager()
