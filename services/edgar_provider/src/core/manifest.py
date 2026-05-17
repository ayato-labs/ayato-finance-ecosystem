import asyncio
import aiohttp
from typing import List, Dict, Any
from loguru import logger

class ManifestLoader:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.base_url = "https://data.sec.gov/submissions"

    async def get_filings_manifest(self, cik: str, form_types: List[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch the submissions manifest for a CIK and filter by form types.
        """
        # CIK must be 10 digits
        cik_padded = cik.zfill(10)
        url = f"{self.base_url}/CIK{cik_padded}.json"
        
        logger.info(f"Fetching manifest from {url}")
        async with self.session.get(url) as resp:
            if resp.status != 200:
                logger.error(f"Failed to fetch manifest for CIK {cik}: {resp.status}")
                return []
            
            data = await resp.json()
            
        filings = data.get("filings", {}).get("recent", {})
        if not filings:
            logger.warning(f"No recent filings found for CIK {cik}")
            return []
            
        results = []
        count = len(filings.get("accessionNumber", []))
        for i in range(count):
            form = filings["form"][i]
            if form_types and form not in form_types:
                continue
                
            results.append({
                "ticker": data.get("tickers", [None])[0],
                "cik": cik,
                "accession_number": filings["accessionNumber"][i],
                "filing_date": filings["filingDate"][i],
                "form": form,
                "primary_document": filings["primaryDocument"][i],
                "is_xbrl": filings["isXBRL"][i],
            })
            
        logger.info(f"Found {len(results)} filings matching criteria for CIK {cik}")
        return results
