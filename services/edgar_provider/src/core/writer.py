import asyncio
import duckdb
from typing import Dict, Any
from loguru import logger
from .dict_manager import DictManager
from .deduplicator import Deduplicator

try:
    from edgar_core.compression import ZstdCompressor
except ImportError:
    logger.warning("edgar_core.compression not found in path. Falling back to mock.")
    class ZstdCompressor:
        def compress(self, data: bytes) -> bytes: return data
        def decompress(self, data: bytes) -> bytes: return data
        def is_using_dict(self) -> bool: return False

class EdgarWriter:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.dict_manager = DictManager()
        
        # Ensure table exists
        con = duckdb.connect(self.db_path)
        con.execute("""
            CREATE TABLE IF NOT EXISTS narratives (
                ticker VARCHAR,
                accession_number VARCHAR,
                section_name VARCHAR,
                content_md_zstd BLOB,
                UNIQUE(ticker, accession_number, section_name)
            )
        """)
        # New tables for deduplication
        con.execute("""
            CREATE TABLE IF NOT EXISTS text_chunks (
                hash VARCHAR PRIMARY KEY,
                content_zstd BLOB
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS narratives_dedup (
                ticker VARCHAR,
                accession_number VARCHAR,
                filing_date VARCHAR,
                section_name VARCHAR,
                chunk_hashes TEXT,
                UNIQUE(ticker, accession_number, section_name)
            )
        """)
        con.close()

    def write_result(self, result: Dict[str, Any]):
        """
        Write parsed results to DuckDB.
        """
        filing = result["filing"]
        sections = result["sections"]
        sic = filing.get("sic")
        compressor = self.dict_manager.get_compressor(sic)
        deduplicator = Deduplicator()
        
        con = duckdb.connect(self.db_path)
        
        for section_name, content_text in sections.items():
            # Deduplicate text
            chunk_hashes, unique_chunks = deduplicator.deduplicate(content_text)
            
            # Save unique chunks
            for h, chunk_content in unique_chunks.items():
                # Check if chunk exists
                exists = con.execute("SELECT 1 FROM text_chunks WHERE hash = ?", (h,)).fetchone()
                if not exists:
                    # Compress chunk
                    raw_bytes = chunk_content.encode("utf-8")
                    compressed_bytes = compressor.compress(raw_bytes)
                    
                    try:
                        con.execute("""
                            INSERT INTO text_chunks (hash, content_zstd)
                            VALUES (?, ?)
                        """, (h, compressed_bytes))
                    except Exception as e:
                        logger.error(f"Failed to save chunk {h}: {e}")
            
            # Save narrative with chunk hashes
            hashes_str = ",".join(chunk_hashes)
            
            try:
                con.execute("""
                    INSERT INTO narratives_dedup (ticker, accession_number, filing_date, section_name, chunk_hashes)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT (ticker, accession_number, section_name) 
                    DO UPDATE SET chunk_hashes = excluded.chunk_hashes, filing_date = excluded.filing_date
                """, (filing["ticker"], filing["accession_number"], filing["filing_date"], section_name, hashes_str))
                logger.info(f"Saved deduplicated {section_name} for {filing['ticker']}")
            except Exception as e:
                logger.error(f"Failed to save deduplicated {section_name} for {filing['ticker']}: {e}")
                
        con.close()

    async def worker(self, input_queue: asyncio.Queue):
        """
        Worker task to consume from input_queue and write to DB.
        Runs as a single worker to serialize writes.
        """
        while True:
            result = await input_queue.get()
            if result is None:
                input_queue.task_done()
                break
                
            # Run sync DB write in executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.write_result, result)
            
            input_queue.task_done()
