import os
import asyncio
from src.edinet_fetcher import EdinetFetcher
from src.edinet_parser import EdinetParser
from dotenv import load_dotenv

async def test_jp_parse():
    load_dotenv()
    fetcher = EdinetFetcher()
    parser = EdinetParser()
    
    doc_id = "S100Y1KO" # 3399
    print(f"Downloading {doc_id}...")
    zip_bytes = fetcher.download_document(doc_id, doc_type=1)
    
    if zip_bytes:
        print(f"Downloaded {len(zip_bytes)} bytes. Parsing...")
        sections = parser.parse_zip(zip_bytes)
        print(f"Extracted sections: {list(sections.keys())}")
        for k, v in sections.items():
            print(f"--- {k} (len: {len(v)}) ---")
            print(v[:200] + "...")
    else:
        print("Failed to download.")

if __name__ == "__main__":
    asyncio.run(test_jp_parse())
