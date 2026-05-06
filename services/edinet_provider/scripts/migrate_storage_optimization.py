import duckdb
import zstandard as zstd
from pathlib import Path
from loguru import logger
import os

# Ensure we are in the right directory
os.chdir(Path(__file__).parent.parent)

def migrate():
    master_path = "data/edinet_master.duckdb"
    reg_path = "data/edinet_registry.duckdb"
    facts_path = "data/edinet_facts.duckdb"
    narr_path = "data/edinet_narratives.duckdb"

    logger.info("Starting storage optimization migration...")
    
    conn = duckdb.connect(master_path)
    conn.execute(f"ATTACH IF NOT EXISTS '{reg_path}' AS registry_db")
    conn.execute(f"ATTACH IF NOT EXISTS '{facts_path}' AS facts_db")
    conn.execute(f"ATTACH IF NOT EXISTS '{narr_path}' AS narr_db")

    # 1. Narratives Migration (BLOB -> VARCHAR with Native ZSTD + ENUM section_name)
    logger.info("Migrating Narratives to Native ZSTD + ENUM...")
    
    # Check if we need to migrate
    tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_catalog = 'narr_db'").fetchall()
    tables = [t[0] for t in tables]
    
    if "narratives" in tables:
        # Check if already migrated
        column_type = conn.execute("SELECT data_type FROM information_schema.columns WHERE table_catalog = 'narr_db' AND table_name = 'narratives' AND column_name = 'content_md'").fetchone()[0]
        if column_type == "VARCHAR":
            logger.info("Narratives already migrated to VARCHAR. Skipping.")
        else:
            # Create ENUM for section_name
            logger.info("Creating section_name_t ENUM...")
            conn.execute("DROP TYPE IF EXISTS narr_db.section_name_t")
            conn.execute("CREATE TYPE narr_db.section_name_t AS ENUM (SELECT DISTINCT section_name FROM narr_db.narratives WHERE section_name IS NOT NULL)")
            
            # Create new table with native ZSTD
            conn.execute("""
                CREATE TABLE narr_db.narratives_new (
                    doc_id VARCHAR NOT NULL,
                    section_name narr_db.section_name_t NOT NULL,
                    content_md VARCHAR NOT NULL,
                    session_id VARCHAR NOT NULL,
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (doc_id, section_name)
                )
            """)
        
        # We must decompress in Python because they were compressed with zstandard library
        logger.info("Decompressing existing narratives (this may take a moment)...")
        existing = conn.execute("SELECT doc_id, section_name, content_md, session_id, ingested_at FROM narr_db.narratives").fetchall()
        
        dctx = zstd.ZstdDecompressor()
        decompressed_batch = []
        for doc_id, section_name, compressed_blob, session_id, ingested_at in existing:
            try:
                # Some might not be compressed if previous migrations were mixed
                if isinstance(compressed_blob, (bytes, bytearray)):
                    content = dctx.decompress(compressed_blob).decode("utf-8")
                else:
                    content = str(compressed_blob)
                decompressed_batch.append((doc_id, section_name, content, session_id, ingested_at))
            except Exception as e:
                logger.warning(f"Failed to decompress {doc_id} {section_name}: {e}. Storing as-is.")
                decompressed_batch.append((doc_id, section_name, str(compressed_blob), session_id, ingested_at))
        
        if decompressed_batch:
            conn.executemany("INSERT INTO narr_db.narratives_new VALUES (?, ?, ?, ?, ?)", decompressed_batch)
        
        conn.execute("DROP TABLE narr_db.narratives")
        conn.execute("ALTER TABLE narr_db.narratives_new RENAME TO narratives")
        logger.info("✅ Narratives migration completed.")

    # 2. Registry ENUM Normalization (Dynamic ENUMs)
    logger.info("Normalizing Registry ENUMs...")
    # Drop existing if any to ensure clean dynamic creation
    conn.execute("DROP TYPE IF EXISTS registry_db.form_code_enum")
    conn.execute("DROP TYPE IF EXISTS registry_db.doc_type_code_enum")
    
    conn.execute("CREATE TYPE registry_db.form_code_enum AS ENUM (SELECT DISTINCT CAST(form_code AS VARCHAR) FROM registry_db.filings WHERE form_code IS NOT NULL)")
    conn.execute("CREATE TABLE registry_db.filings_new AS SELECT * EXCLUDE (form_code, doc_type_code), CAST(form_code AS registry_db.form_code_enum) as form_code, CAST(doc_type_code AS VARCHAR) as doc_type_code FROM registry_db.filings")
    
    conn.execute("CREATE TYPE registry_db.doc_type_code_enum AS ENUM (SELECT DISTINCT doc_type_code FROM registry_db.filings_new WHERE doc_type_code IS NOT NULL)")
    conn.execute("CREATE TABLE registry_db.filings_final AS SELECT * EXCLUDE (doc_type_code), CAST(doc_type_code AS registry_db.doc_type_code_enum) as doc_type_code FROM registry_db.filings_new")
    
    conn.execute("DROP TABLE registry_db.filings")
    conn.execute("DROP TABLE registry_db.filings_new")
    conn.execute("ALTER TABLE registry_db.filings_final RENAME TO filings")
    logger.info("✅ Registry migration completed.")

    # 3. Facts ENUM Normalization + Encoding Fix
    logger.info("Normalizing Facts ENUMs and fixing encoding...")
    conn.execute("DROP TYPE IF EXISTS facts_db.unit_enum")
    conn.execute("DROP TYPE IF EXISTS facts_db.period_enum")
    
    conn.execute("CREATE TABLE facts_db.company_facts_temp AS SELECT * EXCLUDE (unit, fiscal_period), CAST(unit AS VARCHAR) as unit, CAST(fiscal_period AS VARCHAR) as fiscal_period FROM facts_db.company_facts")
    
    # Fix encoding
    conn.execute("UPDATE facts_db.company_facts_temp SET unit = '株' WHERE unit LIKE '%|%' OR unit = '株'")
    conn.execute("UPDATE facts_db.company_facts_temp SET unit = '円' WHERE unit LIKE '%~%' OR unit = '円'")
    
    conn.execute("CREATE TYPE facts_db.unit_enum AS ENUM (SELECT DISTINCT unit FROM facts_db.company_facts_temp WHERE unit IS NOT NULL)")
    conn.execute("CREATE TYPE facts_db.period_enum AS ENUM (SELECT DISTINCT fiscal_period FROM facts_db.company_facts_temp WHERE fiscal_period IS NOT NULL)")
    
    conn.execute("""
        CREATE TABLE facts_db.company_facts_final AS 
        SELECT * EXCLUDE (unit, fiscal_period), 
               CAST(unit AS facts_db.unit_enum) as unit, 
               CAST(fiscal_period AS facts_db.period_enum) as fiscal_period 
        FROM facts_db.company_facts_temp
    """)
    
    conn.execute("DROP TABLE facts_db.company_facts")
    conn.execute("DROP TABLE facts_db.company_facts_temp")
    conn.execute("ALTER TABLE facts_db.company_facts_final RENAME TO company_facts")
    logger.info("✅ Facts migration completed.")

    # 4. Master Ingestion Log ENUM
    logger.info("Normalizing Master Ingestion Log ENUM...")
    conn.execute("DROP TYPE IF EXISTS main.ingestion_status_t")
    tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()
    tables = [t[0] for t in tables]
    if "ingestion_log" in tables:
        conn.execute("CREATE TYPE main.ingestion_status_t AS ENUM ('PENDING', 'SUCCESS', 'PARTIAL_FAIL')")
        conn.execute("CREATE TABLE main.ingestion_log_new AS SELECT * EXCLUDE (status), CAST(status AS main.ingestion_status_t) as status FROM main.ingestion_log")
        conn.execute("DROP TABLE main.ingestion_log")
        conn.execute("ALTER TABLE main.ingestion_log_new RENAME TO ingestion_log")
    
    # Update migration tracking
    conn.execute("INSERT OR REPLACE INTO migrations (name, applied_at) VALUES ('006_storage_optimization_final.py', CURRENT_TIMESTAMP)")
    
    logger.info("🚀 All migrations completed successfully!")
    conn.close()

if __name__ == "__main__":
    migrate()
