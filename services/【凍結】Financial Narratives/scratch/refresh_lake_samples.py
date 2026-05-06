import os
import asyncio
from src.edinet_fetcher import EdinetFetcher
from src.edinet_parser import EdinetParser
from src.edgar_fetcher import EdgarFetcher
from src.edgar_parser import EdgarParser
from src.storage import FinancialNarrativeStorage
from dotenv import load_dotenv

async def refresh_samples():
    load_dotenv()
    
    # 1. Refresh JP Sample (3399) in JP DB
    storage_jp = FinancialNarrativeStorage(market="jp")
    fetcher_jp = EdinetFetcher()
    parser_jp = EdinetParser()
    doc_id_jp = "S100Y1KO"
    print(f"Refreshing JP sample {doc_id_jp}...")
    zip_bytes = fetcher_jp.download_document(doc_id_jp, doc_type=1)
    if zip_bytes:
        sections = parser_jp.parse_zip(zip_bytes)
        metadata = {
            "accessionNumber": doc_id_jp,
            "ticker": "3399",
            "cik": "E03470",
            "form": "120",
            "filingDate": "2026-04-30",
            "filerName": "丸千代山岡家",
        }
        storage_jp.save_filing(metadata, sections)
        print(f"Saved {len(sections)} sections for JP in {storage_jp.db_path}.")

    # 2. Refresh US Sample (AAPL) in US DB
    storage_us = FinancialNarrativeStorage(market="us")
    user_agent = os.getenv("USER_AGENT", "ayato-labs-finance-sync/1.0")
    fetcher_us = EdgarFetcher(user_agent)
    parser_us = EdgarParser()
    ticker = "AAPL"
    print(f"Refreshing US sample {ticker}...")
    filings = fetcher_us.get_latest_submissions(ticker)
    if filings:
        latest = filings[0]
        html_content = fetcher_us.download_filing(latest["accessionNumber"], latest["primaryDocument"])
        if html_content:
            sections = parser_us.extract_all_sections(html_content, latest["form"])
            storage_us.save_filing(latest, sections)
            print(f"Saved {len(sections)} sections for US in {storage_us.db_path}.")

if __name__ == "__main__":
    asyncio.run(refresh_samples())
