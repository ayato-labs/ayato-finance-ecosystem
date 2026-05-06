import os
import re
from pathlib import Path
from typing import List
from loguru import logger
from src.core.db import db_manager
from src.core.schema import TABLE_DEFINITIONS
from src.core.config import settings


class MigrationManager:
    """
    Manages the lifecycle of the Quad-Split database architecture.
    Ensures SSoT schema synchronization and incremental SQL migrations.
    """

    @staticmethod
    def apply_migrations() -> None:
        """Entry point for all database setup and upgrades."""
        logger.info("🚀 Starting Master-led Database Governance migrations...")
        
        with db_manager.connect_master() as conn:
            # 1. Initialize Master Schema (Essential for tracking)
            MigrationManager._init_master_schema(conn)
            
            # 2. Sync Schema-as-Code (SSoT)
            # This ensures tables exist before SQL migrations run
            MigrationManager._sync_ssot_schema(conn)
            
            # 3. Apply Incremental SQL Migrations from directory
            MigrationManager._apply_sql_migrations(conn)

        logger.info("✅ Database Governance and Schema synchronization completed.")

    @staticmethod
    def _init_master_schema(conn) -> None:
        """Ensures the master control tables exist."""
        logger.debug("Initializing Master schema...")
        for t_name, config in TABLE_DEFINITIONS["master"]["tables"].items():
            conn.execute(config["ddl"])

    @staticmethod
    def _sync_ssot_schema(conn) -> None:
        """Synchronizes all shards with the definitions in schema.py."""
        is_memory = str(settings.MASTER_DB_PATH) == ":memory:"
        
        for db_alias in ["registry_db", "facts_db", "narr_db"]:
            logger.debug(f"Synchronizing schema for {db_alias}...")
            for t_name, config in TABLE_DEFINITIONS[db_alias]["tables"].items():
                ddl = config["ddl"]
                # In DuckDB, if attached, we prefix table names with the alias
                if not is_memory:
                    # Basic regex to inject db_alias. before table name if not present
                    # Matches 'CREATE TABLE IF NOT EXISTS table_name'
                    pattern = rf"CREATE TABLE IF NOT EXISTS\s+{t_name}"
                    replacement = f"CREATE TABLE IF NOT EXISTS {db_alias}.{t_name}"
                    ddl = re.sub(pattern, replacement, ddl, flags=re.IGNORECASE)
                
                try:
                    conn.execute(ddl)
                except Exception as e:
                    logger.error(f"Failed to sync SSoT schema for {db_alias}.{t_name}: {e}")
                    raise

    @staticmethod
    def _apply_sql_migrations(conn) -> None:
        """Runs incremental SQL files from the migrations/ directory."""
        migration_dir = Path("migrations")
        if not migration_dir.exists():
            logger.warning(f"Migration directory {migration_dir} not found. Skipping SQL migrations.")
            return

        # Get applied versions
        res = conn.execute("SELECT version FROM schema_version ORDER BY version").fetchall()
        applied_versions = {r[0] for r in res}

        # Find migration files (001_..., 002_...)
        sql_files = sorted(list(migration_dir.glob("*.sql")))
        
        for sql_file in sql_files:
            try:
                version = int(sql_file.name.split("_")[0])
            except (ValueError, IndexError):
                logger.warning(f"Invalid migration filename format: {sql_file.name}. Expected 'NNN_name.sql'")
                continue

            if version not in applied_versions:
                logger.info(f"Applying migration {sql_file.name} (v{version})...")
                sql_content = sql_file.read_text(encoding="utf-8")
                
                try:
                    # Execute as a batch
                    conn.execute(sql_content)
                    # Record success if not already done by the script itself
                    check_res = conn.execute("SELECT 1 FROM schema_version WHERE version = ?", (version,)).fetchone()
                    if not check_res:
                        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
                    logger.info(f"Migration v{version} successful.")
                except Exception as e:
                    logger.error(f"❌ Failed to apply migration {sql_file.name}: {e}")
                    raise
            else:
                logger.debug(f"Migration v{version} already applied.")

if __name__ == "__main__":
    # For testing purposes
    MigrationManager.apply_migrations()
