from pathlib import Path
from loguru import logger
from src.core.db import db_manager
from src.core.schema import TABLE_DEFINITIONS
from src.core.config import settings


class MigrationManager:
    @staticmethod
    def apply_migrations() -> None:
        """Apply migrations using the Quad-Split + Master architecture."""
        logger.info("Applying Master-led Triple-Split Architecture migrations (v6)...")
        
        with db_manager.connect_master() as conn:
            # 1. Initialize Master Schema
            for t_name, config in TABLE_DEFINITIONS["master"]["tables"].items():
                try:
                    conn.execute(config["ddl"])
                except Exception as e:
                    logger.error(f"Failed to execute Master DDL for {t_name}: {e}")
                    raise

            res = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
            current_version = res[0] or 0

            # Version 7: Traceability & Contract Alignment
            if current_version < 7:
                logger.info("Executing Migration v7: Adding session_id for traceability...")
                
                is_memory = str(settings.MASTER_DB_PATH) == ":memory:"
                
                if not is_memory:
                    # Add session_id to company_facts if not exists
                    try:
                        conn.execute("ALTER TABLE facts_db.company_facts ADD COLUMN session_id VARCHAR")
                    except Exception as e:
                        logger.debug(f"session_id might already exist in company_facts: {e}")

                    # Add session_id to narratives if not exists
                    try:
                        conn.execute("ALTER TABLE narr_db.narratives ADD COLUMN session_id VARCHAR")
                    except Exception as e:
                        logger.debug(f"session_id might already exist in narratives: {e}")
                
                # Also ensure all tables from TABLE_DEFINITIONS are created
                for db_alias in ["registry_db", "facts_db", "narr_db"]:
                    for t_name, config in TABLE_DEFINITIONS[db_alias]["tables"].items():
                        ddl = config["ddl"]
                        if not is_memory:
                            ddl = ddl.replace(f"CREATE TABLE IF NOT EXISTS {t_name}", f"CREATE TABLE IF NOT EXISTS {db_alias}.{t_name}")
                        conn.execute(ddl)

                conn.execute("INSERT INTO schema_version (version) VALUES (7)")
                logger.info("Migration v7 successful.")

        logger.info("Governance and Schema synchronization completed.")
