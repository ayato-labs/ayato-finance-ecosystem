from pathlib import Path

import duckdb
from loguru import logger

from src.core.db import db_manager
from src.core.logging import track_performance
from src.core.schema import INDEX_SCHEMAS, TABLE_SCHEMAS


class MigrationManager:
    """
    Lightweight migration engine for DuckDB shards.
    Manages versions per table and applies DDL from SSoT (schema.py).
    """

    @staticmethod
    def _ensure_version_table(conn: duckdb.DuckDBPyConnection):
        """Creates the internal migration tracking table if it doesn't exist."""
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS _schema_version (
                    table_name VARCHAR PRIMARY KEY,
                    current_version VARCHAR,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        except Exception as e:
            logger.error(f"Failed to ensure version table: {e}")
            raise

    @staticmethod
    @track_performance("apply_migrations")
    def apply_migrations(db_path: str | Path, shard_key: str):
        """
        Connects to a shard and synchronizes its tables with the TABLE_SCHEMAS.
        """
        if shard_key not in TABLE_SCHEMAS:
            raise ValueError(f"Unknown shard key: {shard_key}")

        logger.info(f"Checking migrations for shard '{shard_key}' at {db_path}...")

        try:
            with db_manager.connect(db_path, read_only=False) as conn:
                MigrationManager._ensure_version_table(conn)

                # 1. Process Tables
                for table_name, versions in TABLE_SCHEMAS[shard_key].items():
                    target_version = sorted(versions.keys())[-1]

                    res = conn.execute(
                        "SELECT current_version FROM _schema_version WHERE table_name = ?",
                        [table_name],
                    ).fetchone()
                    current_version = res[0] if res else None

                    if current_version != target_version:
                        logger.info(
                            f"  [Migration] {table_name}: {current_version or 'NONE'} "
                            f"-> {target_version}"
                        )

                        table_exists = (
                            conn.execute(
                                "SELECT count(*) FROM information_schema.tables "
                                "WHERE table_name = ?",
                                [table_name],
                            ).fetchone()[0]
                            > 0
                        )

                        if not table_exists:
                            # Clean slate: just run the target DDL
                            conn.execute(versions[target_version])
                        elif shard_key == "jp" and table_name == "company_facts":
                            # Table exists but version is different.
                            logger.warning(
                                f"  [Migration] Upgrading {table_name} to {target_version} "
                                "(DROP & RECREATE for numeric types)"
                            )
                            conn.execute(f"DROP TABLE IF EXISTS {table_name}")
                            conn.execute(versions[target_version])
                        elif target_version == "v1":
                            # Backward compatibility for existing v1 tables
                            logger.info(f"  [Migration] Table {table_name} already exists as v1.")
                        else:
                            logger.warning(
                                f"  [Migration] Unknown upgrade path for {table_name} "
                                f"to {target_version}. Skipping DDL execution."
                            )

                        conn.execute(
                            "INSERT OR REPLACE INTO _schema_version "
                            "(table_name, current_version) VALUES (?, ?)",
                            [table_name, target_version],
                        )

                # 2. Process Indexes (Idempotent)
                if shard_key in INDEX_SCHEMAS:
                    for idx_sql in INDEX_SCHEMAS[shard_key]:
                        try:
                            conn.execute(idx_sql)
                        except Exception as e:
                            # Log and continue for indexes as they might already exist
                            # but we could check for specific 'already exists' error
                            if "already exists" in str(e).lower():
                                logger.debug(
                                    f"  [Migration] Index already exists: {idx_sql[:50]}..."
                                )
                            else:
                                logger.warning(f"  [Migration] Index error: {e}")

            logger.info(f"Migrations for shard '{shard_key}' complete.")

            # Update master registry (if not migrating the master itself)
            if shard_key != "master":
                from src.core.master import master_manager
                master_manager.sync_shard_status(shard_key, Path(db_path))

        except Exception as e:
            logger.error(f"Migration failed for shard '{shard_key}': {e}")
            raise

