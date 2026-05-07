import re
from pathlib import Path
from loguru import logger
from src.infra.db import db_manager

class MigrationManager:
    @staticmethod
    def get_migration_files():
        migration_dir = Path("migrations")
        if not migration_dir.exists():
            return []
        return sorted(list(migration_dir.glob("*.sql")))

    @staticmethod
    def apply_migrations():
        logger.info("Checking for database migrations...")
        files = MigrationManager.get_migration_files()
        
        with db_manager.connect_master() as conn:
            # Create migrations table if not exists
            conn.execute("CREATE TABLE IF NOT EXISTS migrations (name TEXT PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            
            applied = {row[0] for row in conn.execute("SELECT name FROM migrations").fetchall()}
            
            for f in files:
                if f.name not in applied:
                    logger.info(f"Applying migration: {f.name}")
                    try:
                        sql = f.read_text(encoding="utf-8")
                        # DuckDB executemany/execute doesn't support multiple statements in one call easily for some versions
                        # but execute(sql) with multiple ; usually works if they are DDL.
                        # However, to be safe and traceable, we split by ';'
                        statements = [s.strip() for s in re.split(r';\s*', sql) if s.strip()]
                        for stmt in statements:
                            conn.execute(stmt)
                        
                        conn.execute("INSERT INTO migrations (name) VALUES (?)", (f.name,))
                        logger.info(f"✅ Migration {f.name} applied successfully.")
                    except Exception as e:
                        logger.error(f"❌ Failed to apply migration {f.name}: {e}")
                        raise
        logger.info("Database is up to date.")
