import asyncio
import aiohttp
from typing import List, Dict, Any
from loguru import logger

class EdgarDownloader:
    def __init__(self, session: aiohttp.ClientSession, rate_limit: int = 10):
        self.session = session
        self.rate_limit = rate_limit
        self.semaphore = asyncio.Semaphore(rate_limit)
        self.last_request_time = 0

    async def _rate_limit(self):
        # Simple rate limiting: ensure at least 1/rate_limit seconds between requests
        now = asyncio.get_event_loop().time()
        wait_time = (1.0 / self.rate_limit) - (now - self.last_request_time)
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        self.last_request_time = asyncio.get_event_loop().time()

    async def download_filing(self, filing: Dict[str, Any]) -> Dict[str, Any]:
        """
        Download a single filing's primary document.
        """
        # CIK in URL must NOT have leading zeros
        cik_unpadded = str(int(filing["cik"]))
        acc_no = filing["accession_number"].replace("-", "")
        doc = filing["primary_document"]
        
        url = f"https://www.sec.gov/Archives/edgar/data/{cik_unpadded}/{acc_no}/{doc}"
        
        async with self.semaphore:
            await self._rate_limit()
            logger.info(f"Downloading {url}")
            # SEC requires a declared User-Agent
            headers = {
                "User-Agent": "AyatoLabs/1.0 (cwblog69@gmail.com) Python/aiohttp"
            }
            async with self.session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to download {url}: {resp.status}")
                    return None
                    
                content = await resp.read()
                
        return {
            "filing": filing,
            "content": content
        }

    async def worker(self, input_queue: asyncio.Queue, output_queue: asyncio.Queue):
        """
        Worker task to consume from input_queue and produce to output_queue.
        """
        while True:
            filing = await input_queue.get()
            if filing is None: # Sentinel
                input_queue.task_done()
                break
                
            result = await self.download_filing(filing)
            if result:
                await output_queue.put(result)
                
            input_queue.task_done()
