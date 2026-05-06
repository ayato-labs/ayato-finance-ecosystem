import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

import duckdb
from loguru import logger
from src.core.config import settings
from src.core.migrations import MigrationManager

def repair():
    facts_db = settings.FACTS_DB_PATH
    narratives_db = settings.NARRATIVES_DB_PATH

    logger.info("Starting database repair...")

    # 1. Fix Facts DB
    logger.info(f"Repairing {facts_db}...")
    # Remove narratives table if it exists
    with duckdb.connect(str(facts_db)) as conn:
        tables = [r[0] for r in conn.execute("SELECT table_name FROM information_schema.tables").fetchall()]
        if "narratives" in tables:
            logger.warning("Removing incorrect 'narratives' table from facts_db")
            conn.execute("DROP TABLE narratives")
    
    # Run migrations with explicit role
    MigrationManager.apply_migrations(facts_db, role="facts")

    # 2. Fix Narratives DB
    logger.info(f"Repairing {narratives_db}...")
    # Remove facts/tickers/filings tables if they exist
    with duckdb.connect(str(narratives_db)) as conn:
        tables = [r[0] for r in conn.execute("SELECT table_name FROM information_schema.tables").fetchall()]
        for t in ["company_facts", "filings", "tickers"]:
            if t in tables:
                logger.warning(f"Removing incorrect '{t}' table from narratives_db")
                conn.execute(f"DROP TABLE {t}")
    
    # Run migrations with explicit role
    MigrationManager.apply_migrations(narratives_db, role="narratives")

    logger.info("Database repair completed.")

    # 3. Final Verification
    logger.info("Final Verification:")
    with duckdb.connect(str(facts_db)) as conn:
        tables = [r[0] for r in conn.execute("SELECT table_name FROM information_schema.tables").fetchall()]
        logger.info(f"Facts DB Tables: {tables}")
        if "filings" in tables and "company_facts" in tables and "narratives" not in tables:
            logger.info("✅ Facts DB looks correct.")
        else:
            logger.error("❌ Facts DB is still incorrect!")

    with duckdb.connect(str(narratives_db)) as conn:
        tables = [r[0] for r in conn.execute("SELECT table_name FROM information_schema.tables").fetchall()]
        logger.info(f"Narratives DB Tables: {tables}")
        if "narratives" in tables and "company_facts" not in tables:
            logger.info("✅ Narratives DB looks correct.")
        else:
            logger.error("❌ Narratives DB is still incorrect!")

if __name__ == "__main__":
    repair()
