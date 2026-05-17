import asyncio
import duckdb
from typing import Dict, Any
from loguru import logger
from .dict_manager import DictManager

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
        con.close()

    def write_result(self, result: Dict[str, Any]):
        """
        Write parsed results to DuckDB.
        """
        filing = result["filing"]
        sections = result["sections"]
        sic = filing.get("sic")
        compressor = self.dict_manager.get_compressor(sic)
        
        con = duckdb.connect(self.db_path)
        
        for section_name, content_text in sections.items():
            # Compress text
            raw_bytes = content_text.encode("utf-8")
            compressed_bytes = compressor.compress(raw_bytes)
            
            # Upsert into narratives
            try:
                con.execute("""
                    INSERT INTO narratives (ticker, accession_number, section_name, content_md_zstd)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (ticker, accession_number, section_name) 
                    DO UPDATE SET content_md_zstd = excluded.content_md_zstd
                """, (filing["ticker"], filing["accession_number"], section_name, compressed_bytes))
                logger.info(f"Saved {section_name} for {filing['ticker']}")
            except Exception as e:
                logger.error(f"Failed to save {section_name} for {filing['ticker']}: {e}")
                
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
