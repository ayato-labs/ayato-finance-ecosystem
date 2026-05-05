from loguru import logger
from src.core.db import db_manager
from src.core.schema import TABLE_SCHEMAS, INDEX_SCHEMAS

class MigrationManager:
    @staticmethod
    def apply_migrations(db_path):
        logger.info(f"Applying migrations to {db_path}...")
        with db_manager.connect(db_path) as conn:
            for table_name, versions in TABLE_SCHEMAS.items():
                exists = conn.execute(
                    f"SELECT count(*) FROM information_schema.tables WHERE table_name = '{table_name}'"
                ).fetchone()[0] > 0
                if not exists:
                    conn.execute(versions["v1"])
            for index_sql in INDEX_SCHEMAS:
                conn.execute(index_sql)
        logger.info("Migrations complete.")
