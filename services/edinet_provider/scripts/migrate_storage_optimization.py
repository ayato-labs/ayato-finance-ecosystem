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
    conn.execute("DROP TABLE IF EXISTS registry_db.filings_new")
    conn.execute("DROP TABLE IF EXISTS registry_db.filings_final")
    conn.execute("DROP TYPE IF EXISTS registry_db.form_code_enum")
    conn.execute("DROP TYPE IF EXISTS registry_db.doc_type_code_enum")
    
    conn.execute("CREATE TYPE registry_db.form_code_enum AS ENUM (SELECT DISTINCT CAST(form_code AS VARCHAR) FROM registry_db.filings WHERE form_code IS NOT NULL)")
    conn.execute("CREATE TYPE registry_db.doc_type_code_enum AS ENUM (SELECT DISTINCT CAST(doc_type_code AS VARCHAR) FROM registry_db.filings WHERE doc_type_code IS NOT NULL)")
    
    conn.execute("""
        CREATE TABLE registry_db.filings_new (
            doc_id VARCHAR PRIMARY KEY,
            edinet_code VARCHAR,
            sec_code VARCHAR,
            filer_name VARCHAR,
            doc_description VARCHAR,
            submit_datetime TIMESTAMP,
            form_code registry_db.form_code_enum,
            doc_type_code registry_db.doc_type_code_enum,
            session_id VARCHAR,
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.execute("""
        INSERT INTO registry_db.filings_new 
        SELECT doc_id, edinet_code, sec_code, filer_name, doc_description, submit_datetime, 
               CAST(form_code AS registry_db.form_code_enum), 
               CAST(doc_type_code AS registry_db.doc_type_code_enum), 
               session_id, ingested_at 
        FROM registry_db.filings
    """)
    
    conn.execute("DROP TABLE registry_db.filings")
    conn.execute("ALTER TABLE registry_db.filings_new RENAME TO filings")
    logger.info("✅ Registry migration completed.")

    # 3. Facts ENUM Normalization + Encoding Fix
    logger.info("Normalizing Facts ENUMs and fixing encoding...")
    conn.execute("DROP TABLE IF EXISTS facts_db.company_facts_temp")
    conn.execute("DROP TABLE IF EXISTS facts_db.company_facts_final")
    conn.execute("DROP TYPE IF EXISTS facts_db.unit_enum")
    conn.execute("DROP TYPE IF EXISTS facts_db.period_enum")
    
    conn.execute("CREATE TABLE facts_db.company_facts_temp AS SELECT * EXCLUDE (unit, fiscal_period), CAST(unit AS VARCHAR) as unit, CAST(fiscal_period AS VARCHAR) as fiscal_period FROM facts_db.company_facts")
    
    # Fix encoding
    conn.execute("UPDATE facts_db.company_facts_temp SET unit = '株' WHERE unit LIKE '%|%' OR unit = '株'")
    conn.execute("UPDATE facts_db.company_facts_temp SET unit = '円' WHERE unit LIKE '%~%' OR unit = '円'")
    
    conn.execute("CREATE TYPE facts_db.unit_enum AS ENUM (SELECT DISTINCT unit FROM facts_db.company_facts_temp WHERE unit IS NOT NULL)")
    conn.execute("CREATE TYPE facts_db.period_enum AS ENUM (SELECT DISTINCT fiscal_period FROM facts_db.company_facts_temp WHERE fiscal_period IS NOT NULL)")
    
    conn.execute("""
        CREATE TABLE facts_db.company_facts_final (
            doc_id VARCHAR NOT NULL,
            item_name VARCHAR NOT NULL,
            item_value DOUBLE,
            unit facts_db.unit_enum,
            context_id VARCHAR NOT NULL,
            fiscal_year INTEGER,
            fiscal_period facts_db.period_enum,
            session_id VARCHAR,
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (doc_id, item_name, context_id)
        )
    """)
    
    conn.execute("""
        INSERT INTO facts_db.company_facts_final 
        SELECT doc_id, item_name, item_value, 
               CAST(unit AS facts_db.unit_enum), 
               context_id, fiscal_year, 
               CAST(fiscal_period AS facts_db.period_enum), 
               session_id, ingested_at 
        FROM facts_db.company_facts_temp
    """)
    
    conn.execute("DROP TABLE facts_db.company_facts")
    conn.execute("DROP TABLE facts_db.company_facts_temp")
    conn.execute("ALTER TABLE facts_db.company_facts_final RENAME TO company_facts")
    logger.info("✅ Facts migration completed.")

    # 4. Master Ingestion Log ENUM
    logger.info("Normalizing Master Ingestion Log ENUM...")
    conn.execute("DROP TABLE IF EXISTS main.ingestion_log_new")
    conn.execute("DROP TYPE IF EXISTS main.ingestion_status_t")
    tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_catalog = 'edinet_master' AND table_schema = 'main'").fetchall()
    tables = [t[0] for t in tables]
    if "ingestion_log" in tables:
        conn.execute("CREATE TYPE main.ingestion_status_t AS ENUM ('PENDING', 'SUCCESS', 'PARTIAL_FAIL')")
        conn.execute("""
            CREATE TABLE main.ingestion_log_new (
                doc_id VARCHAR PRIMARY KEY,
                status main.ingestion_status_t,
                last_attempt TIMESTAMP,
                retry_count INTEGER DEFAULT 0,
                error_message TEXT
            )
        """)
        conn.execute("""
            INSERT INTO main.ingestion_log_new 
            SELECT doc_id, CAST(status AS main.ingestion_status_t), last_attempt, retry_count, error_message 
            FROM main.ingestion_log
        """)
        conn.execute("DROP TABLE main.ingestion_log")
        conn.execute("ALTER TABLE main.ingestion_log_new RENAME TO ingestion_log")
    
    # Update migration tracking
    conn.execute("INSERT OR REPLACE INTO migrations (name, applied_at) VALUES ('006_storage_optimization_final.py', CURRENT_TIMESTAMP)")
    
    logger.info("🚀 All migrations completed successfully!")
    conn.close()

if __name__ == "__main__":
    migrate()
