from loguru import logger

from src.core.db import db_manager
from src.core.schema import INDEX_SCHEMAS, MIGRATION_HISTORY_SCHEMA, TABLE_SCHEMAS


# Specific migration scripts for each version bump
MIGRATIONS = {
    ("daily_prices", 5): [
        "DROP INDEX IF EXISTS idx_jp_prices_date",
        "ALTER TABLE daily_prices ALTER Open TYPE DECIMAL(18,1)",
        "ALTER TABLE daily_prices ALTER High TYPE DECIMAL(18,1)",
        "ALTER TABLE daily_prices ALTER Low TYPE DECIMAL(18,1)",
        "ALTER TABLE daily_prices ALTER Close TYPE DECIMAL(18,1)",
        "ALTER TABLE daily_prices ALTER AdjustmentOpen TYPE DECIMAL(18,1)",
        "ALTER TABLE daily_prices ALTER AdjustmentHigh TYPE DECIMAL(18,1)",
        "ALTER TABLE daily_prices ALTER AdjustmentLow TYPE DECIMAL(18,1)",
        "ALTER TABLE daily_prices ALTER AdjustmentClose TYPE DECIMAL(18,1)",
        "ALTER TABLE daily_prices ALTER TurnoverValue TYPE DECIMAL(18,1)",
    ],
    ("daily_indices", 2): [
        "ALTER TABLE daily_indices ALTER Open TYPE DECIMAL(18,1)",
        "ALTER TABLE daily_indices ALTER High TYPE DECIMAL(18,1)",
        "ALTER TABLE daily_indices ALTER Low TYPE DECIMAL(18,1)",
        "ALTER TABLE daily_indices ALTER Close TYPE DECIMAL(18,1)",
    ],
    ("dividends", 2): [
        "ALTER TABLE dividends ALTER DividendValue TYPE DECIMAL(18,1)",
    ],
}


class MigrationManager:
    """
    Handles database migrations with version tracking and history logging.
    """

    @staticmethod
    def apply_migrations():
        """
        Applies pending migrations to all designated shard files.
        """
        from src.core.config import settings

        shard_map = {
            "master": settings.JP_MASTER_DB_PATH,
            "prices": settings.JP_PRICES_DB_PATH,
            "financials": settings.JP_FACTS_DB_PATH,
        }

        for shard_name, db_path in shard_map.items():
            logger.info(f"Checking migrations for shard [{shard_name}] at {db_path}...")
            db_path.parent.mkdir(parents=True, exist_ok=True)

            with db_manager.connect(db_path) as conn:
                # 1. Ensure history table exists
                conn.execute(MIGRATION_HISTORY_SCHEMA)

                for table_name, schema_info in TABLE_SCHEMAS.items():
                    # Only apply if the table belongs to this shard
                    if schema_info.get("shard", "master") != shard_name:
                        continue

                    target_version = schema_info["version"]

                    # 2. Get current version from history
                    res = conn.execute(
                        "SELECT version FROM __migrations_history WHERE table_name = ?",
                        (table_name,),
                    ).fetchone()

                    current_version = res[0] if res else 0

                    if current_version < target_version:
                        logger.info(
                            f"Upgrading {table_name}: v{current_version} -> v{target_version}"
                        )

                        # Step-by-step migration from current_version to target_version
                        for v in range(current_version + 1, target_version + 1):
                            # Try to find a specific migration script
                            migration_steps = MIGRATIONS.get((table_name, v))

                            if migration_steps:
                                for step_sql in migration_steps:
                                    try:
                                        conn.execute(step_sql)
                                    except Exception as e:
                                        logger.warning(f"Migration step failed: {step_sql} - {e}")
                            else:
                                # Default: Just run the creation SQL (idempotent)
                                try:
                                    conn.execute(schema_info["sql"])
                                except Exception as e:
                                    logger.warning(
                                        f"Default migration (CREATE) for {table_name} failed: {e}"
                                    )

                        # 3. Update history
                        conn.execute(
                            "INSERT OR REPLACE INTO __migrations_history (table_name, version) "
                            "VALUES (?, ?)",
                            (table_name, target_version),
                        )
                    else:
                        logger.debug(f"Table {table_name} is up to date (v{current_version})")

                # 4. Apply indices (idempotent)
                # Note: For multi-shard, we need to be careful with indices.
                # Here we only apply indices relevant to tables in this shard.
                for index_sql in INDEX_SCHEMAS:
                    # Simple heuristic: if table name is in index SQL, apply it
                    for table_in_shard in [
                        t for t, s in TABLE_SCHEMAS.items() if s.get("shard") == shard_name
                    ]:
                        if table_in_shard in index_sql:
                            try:
                                conn.execute(index_sql)
                            except Exception as e:
                                logger.debug(
                                    f"Index creation skipped or failed (idempotent check): {e}"
                                )
                            break

            logger.info(f"Migrations for [{shard_name}] completed successfully.")

        # 5. Automatically update documentation
        try:
            from scripts.generate_db_docs import generate_markdown

            generate_markdown()
        except Exception as e:
            logger.warning(f"Failed to auto-generate documentation: {e}")
