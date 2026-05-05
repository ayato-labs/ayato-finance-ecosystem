from loguru import logger
from src.core.db import db_manager
from src.core.schema import TABLE_SCHEMAS, INDEX_SCHEMAS, MIGRATION_HISTORY_SCHEMA


class MigrationManager:
    """
    Handles database migrations with version tracking and history logging.
    """

    @staticmethod
    def apply_migrations(db_path, shard_name: str = "default"):
        """
        Applies pending migrations to a specific DuckDB file.
        Uses a history table to ensure idempotency and track versions.
        """
        logger.info(f"Checking migrations for shard [{shard_name}] at {db_path}...")

        with db_manager.connect(db_path) as conn:
            # 1. Ensure history table exists
            conn.execute(MIGRATION_HISTORY_SCHEMA)

            for table_name, schema_info in TABLE_SCHEMAS.items():
                target_version = schema_info["version"]

                # 2. Get current version from history
                res = conn.execute(
                    "SELECT version FROM __migrations_history WHERE table_name = ?", (table_name,)
                ).fetchone()

                current_version = res[0] if res else 0

                if current_version < target_version:
                    logger.info(f"Upgrading {table_name}: v{current_version} -> v{target_version}")

                    # For v1, we just run the create script
                    # For future versions, we would implement incremental alter scripts
                    if current_version == 0:
                        conn.execute(schema_info["sql"])

                    # 3. Update history
                    conn.execute(
                        "INSERT OR REPLACE INTO __migrations_history (table_name, version) VALUES (?, ?)",
                        (table_name, target_version),
                    )
                else:
                    logger.debug(f"Table {table_name} is up to date (v{current_version})")

            # 4. Apply indices (idempotent)
            for index_sql in INDEX_SCHEMAS:
                conn.execute(index_sql)

        logger.info(f"Migrations for [{shard_name}] completed successfully.")
