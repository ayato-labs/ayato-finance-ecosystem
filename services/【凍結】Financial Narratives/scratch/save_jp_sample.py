import os
import asyncio
from src.edinet_fetcher import EdinetFetcher
from src.edinet_parser import EdinetParser
from src.storage import FinancialNarrativeStorage
from dotenv import load_dotenv

async def save_jp_sample():
    load_dotenv()
    fetcher = EdinetFetcher()
    parser = EdinetParser()
    storage = FinancialNarrativeStorage()
    
    doc_id = "S100Y1KO" # 3399
    print(f"Downloading {doc_id}...")
    zip_bytes = fetcher.download_document(doc_id, doc_type=1)
    
    if zip_bytes:
        sections = parser.parse_zip(zip_bytes)
        if sections:
            metadata = {
                "accessionNumber": doc_id,
                "ticker": "3399",
                "cik": "E03470",
                "form": "120", # 有報
                "filingDate": "2026-04-30",
                "filerName": "丸千代山岡家",
            }
            storage.save_filing(metadata, sections)
            print("Saved JP filing to DB.")
        else:
            print("No sections found.")

if __name__ == "__main__":
    asyncio.run(save_jp_sample())
