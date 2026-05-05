from pathlib import Path
from loguru import logger
from src.core.db import db_manager


class MigrationManager:
    @staticmethod
    def apply_migrations(db_path: str | Path) -> None:
        logger.info(f"Checking migrations for {db_path}")
        migrations_dir = Path("migrations")
        if not migrations_dir.exists():
            logger.error(f"Migration directory {migrations_dir} not found")
            return

        with db_manager.connect(db_path) as conn:
            # Create schema_version table if it doesn't exist
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            res = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
            current_version = res[0] or 0

            # Apply missing migrations
            for migration_file in sorted(migrations_dir.glob("*.sql")):
                version = int(migration_file.name.split("_")[0])
                if version > current_version:
                    logger.info(f"Applying migration: {migration_file.name}")
                    with open(migration_file, "r", encoding="utf-8") as f:
                        sql = f.read()
                        conn.execute(sql)
                    logger.info(f"Migration {migration_file.name} applied")

        logger.info("Migrations completed.")
