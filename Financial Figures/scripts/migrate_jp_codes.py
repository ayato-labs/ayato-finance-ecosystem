import duckdb
from src.core.config import settings
from loguru import logger

def migrate_db(db_path, name):
    logger.info(f"Starting migration for {name} ({db_path})...")
    try:
        conn = duckdb.connect(str(db_path))
        
        # Check if tickers table exists (only in jp.duckdb)
        tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
        
        if "company_facts" in tables:
            logger.info(f"Dropping indexes for {name}...")
            if name == "JP Market DB":
                conn.execute("DROP INDEX IF EXISTS idx_jp_facts_lookup")
                conn.execute("DROP INDEX IF EXISTS idx_jp_tickers_symbol")
            else:
                conn.execute("DROP INDEX IF EXISTS idx_edinet_facts_lookup")

        if "tickers" in tables:
            logger.info(f"Normalizing 'tickers' table in {name} using table recreation...")
            # Backup
            conn.execute("ALTER TABLE tickers RENAME TO tickers_old")
            # Create fresh with schema
            conn.execute("""
                CREATE TABLE tickers (
                    code VARCHAR PRIMARY KEY,
                    name VARCHAR,
                    market_section VARCHAR,
                    sector VARCHAR,
                    last_session_id VARCHAR
                )
            """)
            # Insert normalized
            conn.execute("""
                INSERT OR IGNORE INTO tickers 
                SELECT DISTINCT 
                    CASE 
                        WHEN LENGTH(code) = 5 AND code LIKE '%0' THEN SUBSTR(code, 1, 4) 
                        ELSE code 
                    END as code, 
                    name, market_section, sector, last_session_id 
                FROM tickers_old
            """)
            conn.execute("DROP TABLE tickers_old")
            count = conn.execute("SELECT count(*) FROM tickers").fetchone()[0]
            logger.info(f"Ticker normalization complete. Total tickers: {count}")

        if "company_facts" in tables:
            logger.info(f"Normalizing 'company_facts' table in {name}...")
            # Backup
            conn.execute("ALTER TABLE company_facts RENAME TO company_facts_old")
            # Create fresh with schema
            conn.execute("""
                CREATE TABLE company_facts (
                    fact_id VARCHAR PRIMARY KEY,
                    code VARCHAR,
                    disclosed_date DATE,
                    fiscal_year INTEGER,
                    fiscal_period VARCHAR,
                    taxonomy VARCHAR,
                    tag VARCHAR,
                    label VARCHAR,
                    value DOUBLE,
                    unit VARCHAR,
                    accession_number VARCHAR,
                    session_id VARCHAR,
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Insert normalized
            conn.execute("""
                INSERT OR IGNORE INTO company_facts (
                    fact_id, code, disclosed_date, fiscal_year, fiscal_period, 
                    taxonomy, tag, label, value, unit, accession_number, session_id, ingested_at
                )
                SELECT 
                    fact_id, 
                    CASE 
                        WHEN LENGTH(code) = 5 AND code LIKE '%0' THEN SUBSTR(code, 1, 4) 
                        ELSE code 
                    END as code, 
                    disclosed_date, fiscal_year, fiscal_period, 
                    taxonomy, tag, label, value, unit, accession_number, session_id, ingested_at
                FROM company_facts_old
            """)
            conn.execute("DROP TABLE company_facts_old")
            count = conn.execute("SELECT count(*) FROM company_facts WHERE LENGTH(code) = 4").fetchone()[0]
            logger.info(f"Fact normalization complete for {name}. Total 4-digit facts: {count}")
            
            # Recreate indexes
            logger.info("Recreating indexes...")
            if name == "JP Market DB":
                conn.execute("CREATE INDEX IF NOT EXISTS idx_jp_facts_lookup ON company_facts (code, tag, disclosed_date)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_jp_tickers_symbol ON tickers (code)")
            else:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_edinet_facts_lookup ON company_facts (code, tag, disclosed_date)")

        conn.close()
        logger.info(f"Migration successful for {name}.")
    except Exception as e:
        logger.error(f"Migration failed for {name}: {e}")

if __name__ == "__main__":
    migrate_db(settings.DB_PATH_JP, "JP Market DB")
    migrate_db(settings.DB_PATH_EDINET, "EDINET DB")
