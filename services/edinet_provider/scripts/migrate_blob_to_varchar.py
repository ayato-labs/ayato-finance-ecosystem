import time
import zstandard as zstd
from loguru import logger

from src.datalake.engine import JPEDINETEngine
from src.datalake.shared.infra.db import db_manager

def run_migration():
    logger.info("Initializing engine...")
    engine = JPEDINETEngine()
    
    logger.info("Starting STREAMING narratives data migration (BLOB -> VARCHAR via Table Copy)...")
    
    dctx = zstd.ZstdDecompressor()
    chunk_size = 50000
    
    # Rebuild narratives_new from scratch to ensure complete consistency
    with db_manager.connect_master(read_only=False) as conn:
        logger.info("Re-creating temporary narratives_new table...")
        conn.execute("DROP TABLE IF EXISTS narr_db.narratives_new")
        conn.execute("""
            CREATE TABLE narr_db.narratives_new (
                doc_id VARCHAR,
                section_name VARCHAR,
                content_md VARCHAR, -- VARCHAR instead of BLOB
                session_id VARCHAR,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(doc_id, section_name)
            )
        """)
        
        total_rows = conn.execute("SELECT COUNT(*) FROM narr_db.narratives").fetchone()[0]
        logger.info(f"Total rows to migrate: {total_rows:,}")
        
    t0 = time.time()
    offset = 0
    
    # Use a single connection and a dedicated streaming cursor
    with db_manager.connect_master(read_only=False) as conn:
        cursor = conn.cursor()
        # Streaming query without ORDER BY or LIMIT/OFFSET (highly efficient)
        cursor.execute("""
            SELECT doc_id, section_name, content_text, content_md, session_id, ingested_at
            FROM narr_db.narratives
        """)
        
        while True:
            records = cursor.fetchmany(chunk_size)
            if not records:
                break
                
            logger.info(f"Fetched chunk of {len(records):,} records. Decompressing...")
            
            bulk_data = []
            for doc_id, sec_name, pre_decomp, comp_bytes, sess_id, ing_at in records:
                # Use previously decompressed VARCHAR if available
                if pre_decomp is not None:
                    decompressed = pre_decomp
                elif comp_bytes is not None:
                    try:
                        decompressed = dctx.decompress(comp_bytes).decode("utf-8")
                    except Exception as dec_err:
                        logger.warning(f"Decompression failed for {doc_id}/{sec_name}: {dec_err}. Storing empty.")
                        decompressed = ""
                else:
                    decompressed = ""
                    
                bulk_data.append((doc_id, sec_name, decompressed, sess_id, ing_at))
            
            logger.info(f"Inserting {len(bulk_data):,} records into narratives_new...")
            # Insert bulk data into the new table
            conn.executemany("""
                INSERT INTO narr_db.narratives_new (doc_id, section_name, content_md, session_id, ingested_at)
                VALUES (?, ?, ?, ?, ?)
            """, bulk_data)
            
            offset += len(records)
            elapsed = time.time() - t0
            progress = offset / total_rows * 100
            rate = offset / elapsed if elapsed > 0 else 0
            eta = (total_rows - offset) / rate / 60 if rate > 0 else 0
            logger.info(f"Progress: {progress:.1f}% ({offset:,}/{total_rows:,}). Elapsed: {elapsed/60:.1f}m. Rate: {rate:.0f} rows/s. ETA: {eta:.1f}m")
            
    # Perform final table swap
    logger.info("All records copied. Performing final table swap...")
    with db_manager.connect_master(read_only=False) as conn:
        try:
            conn.execute("DROP TABLE narr_db.narratives")
            conn.execute("ALTER TABLE narr_db.narratives_new RENAME TO narratives")
            logger.info("✅ Table swap successful! narr_db.narratives is now a VARCHAR table.")
        except Exception as swap_err:
            logger.error(f"Table swap failed: {swap_err}")
            raise

if __name__ == "__main__":
    run_migration()
