import asyncio
import aiohttp
from typing import List, Dict, Any
from loguru import logger

from .manifest import ManifestLoader
from .downloader import EdgarDownloader
from .parser import EdgarParser
from .writer import EdgarWriter

class EdgarPipeline:
    def __init__(self, db_path: str, rate_limit: int = 10):
        self.db_path = db_path
        self.rate_limit = rate_limit

    async def run(self, ciks: List[str], form_types: List[str] = None):
        """
        Run the pipeline for a list of CIKs.
        """
        async with aiohttp.ClientSession() as session:
            # 1. Initialize queues
            download_queue = asyncio.Queue()
            parse_queue = asyncio.Queue()
            write_queue = asyncio.Queue()

            # 2. Instantiate components
            manifest_loader = ManifestLoader(session)
            downloader = EdgarDownloader(session, self.rate_limit)
            parser = EdgarParser()
            writer = EdgarWriter(self.db_path)

            # 3. Start workers
            # Multiple downloaders and parsers can run in parallel
            downloader_tasks = [
                asyncio.create_task(downloader.worker(download_queue, parse_queue))
                for _ in range(5) # 5 concurrent downloaders
            ]
            parser_tasks = [
                asyncio.create_task(parser.worker(parse_queue, write_queue))
                for _ in range(3) # 3 concurrent parsers
            ]
            # Single writer to serialize DB access
            writer_task = asyncio.create_task(writer.worker(write_queue))

            # 4. Feed manifest to download queue
            for cik in ciks:
                manifest = await manifest_loader.get_filings_manifest(cik, form_types)
                for filing in manifest:
                    await download_queue.put(filing)

            # 5. Wait for download queue to be processed
            await download_queue.join()
            
            # Send sentinel to stop downloaders
            for _ in range(len(downloader_tasks)):
                await download_queue.put(None)
            await asyncio.gather(*downloader_tasks)

            # Wait for parse queue to be processed
            await parse_queue.join()
            
            # Send sentinel to stop parsers
            for _ in range(len(parser_tasks)):
                await parse_queue.put(None)
            await asyncio.gather(*parser_tasks)

            # Wait for write queue to be processed
            await write_queue.join()
            
            # Send sentinel to stop writer
            await write_queue.put(None)
            await writer_task

            logger.info("Pipeline finished successfully!")
