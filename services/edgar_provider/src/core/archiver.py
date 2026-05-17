import duckdb
import os
from datetime import datetime, timedelta
from loguru import logger

class Archiver:
    def __init__(self, db_path: str = "data/edgar.duckdb", archives_dir: str = "data/archives"):
        self.db_path = db_path
        self.archives_dir = archives_dir
        os.makedirs(self.archives_dir, exist_ok=True)

    def archive_old_data(self, years_threshold: int = 3):
        """
        Export data older than years_threshold to Parquet and remove from DB.
        """
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=years_threshold * 365)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")
        
        logger.info(f"Archiving data older than {cutoff_str} (Threshold: {years_threshold} years)")
        
        con = duckdb.connect(self.db_path)
        
        # Check if table exists
        exists = con.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'narratives_dedup'").fetchone()
        if not exists:
            logger.warning("Table narratives_dedup does not exist. Nothing to archive.")
            con.close()
            return
            
        # Count rows to archive
        count = con.execute("SELECT COUNT(*) FROM narratives_dedup WHERE filing_date < ?", (cutoff_str,)).fetchone()[0]
        if count == 0:
            logger.info("No data to archive.")
            con.close()
            return
            
        logger.info(f"Found {count} narratives to archive.")
        
        # Paths
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        narratives_parquet = os.path.join(self.archives_dir, f"narratives_archive_{timestamp}.parquet")
        chunks_parquet = os.path.join(self.archives_dir, f"chunks_archive_{timestamp}.parquet")
        
        try:
            # Export narratives
            logger.info(f"Exporting narratives to {narratives_parquet}")
            con.execute(f"""
                COPY (SELECT * FROM narratives_dedup WHERE filing_date < '{cutoff_str}') 
                TO '{narratives_parquet}' (FORMAT PARQUET)
            """)
            
            # Export referenced chunks
            logger.info(f"Exporting referenced chunks to {chunks_parquet}")
            con.execute(f"""
                COPY (
                    SELECT * FROM text_chunks 
                    WHERE hash IN (
                        SELECT UNNEST(STRING_SPLIT(chunk_hashes, ',')) 
                        FROM narratives_dedup 
                        WHERE filing_date < '{cutoff_str}'
                    )
                ) 
                TO '{chunks_parquet}' (FORMAT PARQUET)
            """)
            
            # Delete from narratives_dedup
            logger.info("Deleting archived narratives from DB")
            con.execute("DELETE FROM narratives_dedup WHERE filing_date < ?", (cutoff_str,))
            
            # Garbage collect chunks (optional but good)
            logger.info("Cleaning up unreferenced chunks")
            con.execute("""
                DELETE FROM text_chunks 
                WHERE hash NOT IN (
                    SELECT UNNEST(STRING_SPLIT(chunk_hashes, ',')) 
                    FROM narratives_dedup
                )
            """)
            
            logger.info("Archiving completed successfully.")
            
        except Exception as e:
            logger.error(f"Archiving failed: {e}")
            # In a production system, we might want to rollback or handle failures more carefully
            
        finally:
            con.close()
            
    def query_archive(self, parquet_path: str, query: str):
        """
        Helper to run a query on an archived Parquet file.
        """
        con = duckdb.connect(":memory:")
        try:
            # DuckDB can query Parquet files directly by referencing the path!
            result = con.execute(query.replace("narratives_archive", f"'{parquet_path}'")).fetchall()
            return result
        except Exception as e:
            logger.error(f"Failed to query archive: {e}")
        finally:
            con.close()
