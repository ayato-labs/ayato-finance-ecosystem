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

            # Version 6: Full Governance Implementation
            if current_version < 6:
                logger.info("Executing Migration v6: Schema-as-Code & Multi-DB Governance...")
                
                # Check if we are in memory (TESTING) or file-based
                is_memory = str(settings.MASTER_DB_PATH) == ":memory:"
                
                # Setup sub-databases using the definitions in schema.py
                for db_alias in ["registry_db", "facts_db", "narr_db"]:
                    for t_name, config in TABLE_DEFINITIONS[db_alias]["tables"].items():
                        ddl = config["ddl"]
                        
                        if is_memory:
                            # In memory, all tables go to 'main' without prefixes
                            target = f"CREATE TABLE IF NOT EXISTS {t_name}"
                            if f"CREATE TABLE IF NOT EXISTS {t_name}" in ddl:
                                ddl = ddl.replace(f"CREATE TABLE IF NOT EXISTS {t_name}", target)
                            else:
                                ddl = ddl.replace(f"CREATE TABLE {t_name}", target)
                        else:
                            # File-based, use alias prefixes
                            target = f"CREATE TABLE IF NOT EXISTS {db_alias}.{t_name}"
                            if f"CREATE TABLE IF NOT EXISTS {t_name}" in ddl:
                                ddl = ddl.replace(f"CREATE TABLE IF NOT EXISTS {t_name}", target)
                            else:
                                ddl = ddl.replace(f"CREATE TABLE {t_name}", target)
                            
                        try:
                            conn.execute(ddl)
                        except Exception as e:
                            logger.error(f"Failed to execute DDL for {db_alias}.{t_name}: {e}")
                            raise
                
                conn.execute("INSERT INTO schema_version (version) VALUES (6)")
                logger.info("Migration v6 successful.")

        logger.info("Governance and Schema synchronization completed.")
