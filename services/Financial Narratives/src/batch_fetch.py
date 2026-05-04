import asyncio
import json
import os
import time
from datetime import date, timedelta

from loguru import logger

from src.edgar_fetcher import EdgarFetcher
from src.edgar_parser import EdgarParser
from src.edinet_fetcher import EdinetFetcher
from src.edinet_parser import EdinetParser
from src.logging_utils import log_memory_usage
from src.storage import FinancialNarrativeStorage
from src.structurer import FilingStructurer

USER_AGENT = "SampleAgent yourname@example.com"
TICKERS = ["AAPL", "NVDA", "7203", "9984"]

async def batch_fetch(tickers: list[str] = None, run_structuring: bool = False):
    storage = FinancialNarrativeStorage()
    edgar_fetcher = EdgarFetcher(USER_AGENT)
    edgar_parser = EdgarParser()
    edinet_fetcher = EdinetFetcher()
    edinet_parser = EdinetParser()
    structurer = FilingStructurer(os.environ.get("GOOGLE_API_KEY")) if os.environ.get("GOOGLE_API_KEY") else None

    if tickers:
        for ticker in tickers:
            try:
                logger.info(f"=== Processing {ticker} (On-demand) ===")
                is_jp = ticker.isdigit()
                if is_jp:
                    await process_jp_ticker(
                        ticker, edinet_fetcher, edinet_parser, storage, run_structuring
                    )
                else:
                    await process_us_ticker(
                        ticker, edgar_fetcher, edgar_parser, storage, run_structuring
                    )
                log_memory_usage()
            except Exception as e:
                logger.error(f"Failed to process {ticker}: {e}")
    else:
        logger.info("=== Starting Automated Sync for All Listed Companies ===")
        await sync_recent_jp_filings(edinet_fetcher, edinet_parser, storage, run_structuring=run_structuring)
        await sync_recent_us_filings(
            edgar_fetcher, edgar_parser, storage, run_structuring=run_structuring
        )


async def sync_recent_jp_filings(fetcher, parser, storage, days=7, run_structuring=False):
    today = date.today()
    for i in range(days):
        target_date = today - timedelta(days=i)
        logger.info(f"Checking EDINET filings for {target_date}")
        docs = fetcher.list_documents(target_date)
        
        for doc in docs:
            if doc.get("docTypeCode") == "120":
                doc_id = doc.get("docID")
                ticker = doc.get("secCode", "0000")[:4]
                if not storage.filing_exists(doc_id):
                    logger.info(f"New JP filing found: {doc_id} (Ticker: {ticker})")
                    zip_bytes = fetcher.download_document(doc_id)
                    sections = parser.parse_xbrl_zip(zip_bytes)
                    metadata = {
                        "accessionNumber": doc_id,
                        "ticker": ticker,
                        "form": "Yuho",
                        "filingDate": doc.get("filingDate"),
                        "filerName": doc.get("filerName"),
                    }
                    storage.save_filing(metadata, sections)
                    if run_structuring:
                        await run_structuring_for_filing(ticker, doc_id, sections, storage)

            time.sleep(0.1)


async def sync_recent_us_filings(fetcher, parser, storage, run_structuring=False):
    default_tickers = ["AAPL", "NVDA", "GOOGL", "AMZN", "META", "MSFT", "TSLA"]
    for ticker in default_tickers:
        await process_us_ticker(ticker, fetcher, parser, storage, run_structuring)


async def process_us_ticker(ticker, fetcher, parser, storage, run_structuring=False):
    subs = fetcher.get_latest_submissions(ticker)
    cik = fetcher.get_cik(ticker)
    relevant = fetcher.filter_relevant_filings(subs)

    for filing in relevant:
        acc_no = filing["accessionNumber"]
        if storage.filing_exists(acc_no):
            continue

        logger.info(f"Processing new US filing: {acc_no} for {ticker}")
        primary_doc = filing["primaryDocument"]
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no.replace('-', '')}/{primary_doc}"
        
        import requests
        resp = requests.get(url, headers={"User-Agent": USER_AGENT})
        if resp.status_code != 200:
            logger.error(f"Failed to download {url}: {resp.status_code}")
            continue

        sections = parser.extract_all_sections(resp.text)
        filing_metadata = filing.copy()
        filing_metadata["ticker"] = ticker
        filing_metadata["cik"] = cik
        storage.save_filing(filing_metadata, sections)
        if run_structuring:
            await run_structuring_for_filing(ticker, acc_no, sections, storage)

    time.sleep(0.5)


async def process_jp_ticker(ticker, fetcher, parser, storage, run_structuring=False):
    edinet_code = fetcher.get_edinet_code(ticker)
    if not edinet_code:
        logger.warning(f"No EDINET code found for {ticker}")
        return

    today = date.today()
    docs = fetcher.list_documents(today - timedelta(days=365))
    found_doc = None
    for doc in docs:
        if doc.get("edinetCode") == edinet_code and doc.get("docTypeCode") == "120":
            found_doc = doc
            break

    if found_doc:
        doc_id = found_doc.get("docID")
        if not storage.filing_exists(doc_id):
            zip_bytes = fetcher.download_document(doc_id)
            sections = parser.parse_xbrl_zip(zip_bytes)
            metadata = {
                "accessionNumber": doc_id,
                "ticker": ticker,
                "form": "Yuho",
                "filingDate": found_doc.get("filingDate"),
                "filerName": found_doc.get("filerName"),
            }
            storage.save_filing(metadata, sections)
            if run_structuring:
                await run_structuring_for_filing(ticker, doc_id, sections, storage)

    time.sleep(0.5)


async def run_structuring_for_filing(ticker, acc_no, sections, storage):
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("GOOGLE_API_KEY not set, skipping structuring.")
        return

    existing_facts = storage.get_structuring_by_ticker(ticker)
    if existing_facts:
        logger.info(f"Structured facts already exist for {ticker}. Skipping.")
        return

    try:
        from src.structurer import FilingStructurer
        structurer = FilingStructurer(api_key=api_key)
        facts = await structurer.extract_facts(sections)
        if facts:
            storage.save_structuring(acc_no, ticker, facts)
            logger.info(f"Structured facts saved for {ticker} ({acc_no})")
    except Exception as e:
        logger.error(f"Failed to structure {ticker}: {e}")


if __name__ == "__main__":
    import sys
    asyncio.run(batch_fetch(TICKERS if len(sys.argv) > 1 else None))
