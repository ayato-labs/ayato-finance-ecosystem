import asyncio
import re
from typing import Dict, Any
from loguru import logger

class EdgarParser:
    def __init__(self):
        # Simple regex to find sections. 
        # This is a very simplified heuristic and will not work for all filings!
        self.risk_factors_regex = re.compile(r"Item\s*1A\.?\s*Risk\s*Factors", re.IGNORECASE)
        self.mda_regex = re.compile(r"Item\s*7\.?\s*Management.*?Discussion", re.IGNORECASE)

    def parse_content(self, raw_content: bytes) -> Dict[str, str]:
        """
        Parse raw HTML/Text content and extract sections.
        This is a simplified implementation.
        """
        try:
            text = raw_content.decode("utf-8", errors="ignore")
        except Exception as e:
            logger.error(f"Failed to decode content: {e}")
            return {}

        # Strip some common HTML tags to make regex easier (very naive)
        clean_text = re.sub(r"<[^>]+>", " ", text)
        clean_text = re.sub(r"\s+", " ", clean_text)

        sections = {}
        
        # Try to find Risk Factors
        risk_match = self.risk_factors_regex.search(clean_text)
        if risk_match:
            start = risk_match.start()
            next_item = re.search(r"Item\s*\d", clean_text[start+20:])
            if next_item:
                end = start + 20 + next_item.start()
            else:
                end = start + 50000 # Fallback length
            sections["Risk Factors"] = clean_text[start:end].strip()

        # Try to find MD&A
        mda_match = self.mda_regex.search(clean_text)
        if mda_match:
            start = mda_match.start()
            next_item = re.search(r"Item\s*\d", clean_text[start+20:])
            if next_item:
                end = start + 20 + next_item.start()
            else:
                end = start + 50000
            sections["MD&A"] = clean_text[start:end].strip()

        return sections

    async def worker(self, input_queue: asyncio.Queue, output_queue: asyncio.Queue):
        """
        Worker task to consume from input_queue and produce to output_queue.
        """
        while True:
            item = await input_queue.get()
            if item is None:
                input_queue.task_done()
                break
                
            filing = item["filing"]
            content = item["content"]
            
            logger.info(f"Parsing filing {filing['accession_number']}")
            
            # Run CPU-bound parsing in executor
            loop = asyncio.get_running_loop()
            sections = await loop.run_in_executor(None, self.parse_content, content)
            
            if sections:
                await output_queue.put({
                    "filing": filing,
                    "sections": sections
                })
            else:
                logger.warning(f"No sections extracted from filing {filing['accession_number']}")
                
            input_queue.task_done()
