import asyncio
import gc
import os
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from loguru import logger
from dotenv import load_dotenv

# .envファイルをロード
load_dotenv()

from src.config import SEC_TICKERS, USER_AGENT
from src.edgar_fetcher import EdgarFetcher
from src.edgar_parser import EdgarParser
from src.edinet_fetcher import EdinetFetcher
from src.edinet_parser import EdinetParser
from src.storage import FinancialNarrativeStorage

# デフォルト銘柄リスト
TICKERS = ["AAPL", "NVDA", "7203", "9984"]

# 同時実行数の制御
MAX_CONCURRENT_JP_DOCS = 5
MAX_CONCURRENT_US_TICKERS = 10

jp_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JP_DOCS)
us_semaphore = asyncio.Semaphore(MAX_CONCURRENT_US_TICKERS)
jp_db_write_lock = asyncio.Lock()
us_db_write_lock = asyncio.Lock()


async def batch_fetch(tickers: list[str] | None = None, days: int = 7):
    """
    日米市場の定性データを一括取得・Data Lake(DuckDB)へ保存する。
    構造化は別プロセスのReconciler/Workerに委譲するためここでは行わない。
    """
    logger.info(f"Starting batch_fetch (Ingestion Only) | tickers_specified={tickers is not None} | days={days}")

    storage_jp = FinancialNarrativeStorage(market="jp")
    storage_us = FinancialNarrativeStorage(market="us")
    edgar_fetcher = EdgarFetcher(USER_AGENT)
    edgar_parser = EdgarParser()
    edinet_fetcher = EdinetFetcher()
    edinet_parser = EdinetParser()

    try:
        if tickers:
            # 1. 特定銘柄のオンデマンド処理
            for ticker in tickers:
                try:
                    logger.info(f"Processing ticker (on-demand) | ticker={ticker}")
                    is_jp = ticker.isdigit()
                    if is_jp:
                        await process_jp_ticker(ticker, edinet_fetcher, edinet_parser, storage_jp)
                    else:
                        await process_us_ticker(ticker, edgar_fetcher, edgar_parser, storage_us, days=3650)
                    gc.collect()
                except Exception:
                    logger.exception(f"Unexpected error processing ticker | ticker={ticker}")
        else:
            # 2. 自動同期 (全上場企業対象)
            logger.info(f"Starting automated parallel sync | lookback_days={days}")
            
            tasks = [
                sync_recent_jp_filings(edinet_fetcher, edinet_parser, storage_jp, days=days),
                sync_recent_us_filings(edgar_fetcher, edgar_parser, storage_us, days=days)
            ]
            
            try:
                await asyncio.gather(*tasks)
            except Exception:
                logger.exception("Global failure during parallel market synchronization")

    except Exception:
        logger.exception("Critical error in batch_fetch orchestration")


async def sync_recent_jp_filings(fetcher, parser, storage, days=7):
    today = date.today()

    async def process_jp_doc(doc):
        async with jp_semaphore:
            try:
                doc_id = doc.get("docID")
                if not doc_id:
                    return
                
                if doc.get("xbrlFlag") != "1":
                    return

                ticker = (doc.get("secCode") or "")[:4]
                if not ticker:
                    ticker = doc.get("edinetCode") or "UNKNOWN"
                
                if storage.filing_exists(doc_id):
                    return

                logger.info(f"Downloading JP filing | filer={doc.get('filerName')} | doc_id={doc_id}")
                zip_bytes = await asyncio.to_thread(fetcher.download_document, doc_id, doc_type=1)
                
                if zip_bytes:
                    sections = await asyncio.to_thread(parser.parse_zip, zip_bytes)
                    if sections:
                        metadata = {
                            "accessionNumber": doc_id,
                            "ticker": ticker,
                            "cik": doc.get("edinetCode"),
                            "form": doc.get("formCode"),
                            "filingDate": doc.get("filingDate"),
                            "filerName": doc.get("filerName"),
                        }
                        async with jp_db_write_lock:
                            await asyncio.to_thread(storage.save_filing, metadata, sections)
                            
                    del zip_bytes
                    gc.collect()
            except Exception:
                logger.exception(f"Error processing JP document | doc_id={doc.get('docID')}")

    for i in range(days):
        target_date = today - timedelta(days=i)
        logger.info(f"Syncing JP filings | date={target_date}")
        
        try:
            docs = await asyncio.to_thread(fetcher.list_documents, target_date)
            if not docs:
                continue
                
            relevant_docs = [d for d in docs if d.get("xbrlFlag") == "1"]
            if relevant_docs:
                tasks = [process_jp_doc(doc) for doc in relevant_docs]
                await asyncio.gather(*tasks)
        except Exception:
            logger.exception(f"Failed to fetch JP document list | date={target_date}")


async def sync_recent_us_filings(fetcher, parser, storage, days=7):
    try:
        all_tickers = fetcher.get_all_tickers()
        logger.info(f"Scanning US tickers | count={len(all_tickers)} | days={days}")

        for ticker in all_tickers:
            try:
                await process_us_ticker(ticker, fetcher, parser, storage, days=days)
                await asyncio.sleep(0.11)
            except Exception:
                logger.exception(f"Unexpected error in US ticker loop | ticker={ticker}")
                
    except Exception:
        logger.exception("Critical failure during US ticker list retrieval")


async def process_us_ticker(ticker, fetcher, parser, storage, days=7):
    try:
        subs = await asyncio.to_thread(fetcher.get_latest_submissions, ticker)
        if not subs:
            return

        filings = fetcher.filter_relevant_filings(subs, doc_types=None)
        if not filings:
            return

        threshold_date = (date.today() - timedelta(days=days)).isoformat()
        target_filings = [f for f in filings if f["filingDate"] >= threshold_date]

        for filing in target_filings:
            try:
                acc_no = filing["accessionNumber"]
                if storage.filing_exists(acc_no):
                    continue

                cik = fetcher.get_cik(ticker).lstrip("0")
                acc_no_clean = acc_no.replace("-", "")
                doc_name = filing["primaryDocument"]
                url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_clean}/{doc_name}"

                logger.info(f"Downloading US filing | ticker={ticker} | acc_no={acc_no}")
                resp = await asyncio.to_thread(requests.get, url, headers=fetcher.headers, timeout=30)
                await asyncio.sleep(0.1)

                if resp.status_code != 200:
                    continue

                sections = await asyncio.to_thread(parser.extract_all_sections, resp.text, filing["form"])
                if sections:
                    filing_metadata = filing.copy()
                    filing_metadata["ticker"] = ticker
                    filing_metadata["cik"] = cik
                    
                    async with us_db_write_lock:
                        await asyncio.to_thread(storage.save_filing, filing_metadata, sections)

                del resp
                gc.collect()
            except Exception:
                logger.exception(f"Error processing US filing | ticker={ticker} | acc_no={filing.get('accessionNumber')}")

    except Exception:
        logger.exception(f"Failed to process US ticker | ticker={ticker}")


async def process_jp_ticker(ticker, fetcher, parser, storage):
    try:
        edinet_code = fetcher.get_edinet_code(ticker)
        if not edinet_code:
            return

        today = date.today()
        found_doc = None
        for i in range(365):
            target_date = today - timedelta(days=i)
            docs = fetcher.list_documents(target_date)
            for doc in docs:
                if doc.get("edinetCode") == edinet_code and doc.get("docTypeCode") == "120":
                    found_doc = doc
                    break
            if found_doc:
                break

        if not found_doc:
            return

        doc_id = found_doc["docID"]
        if storage.filing_exists(doc_id):
            return

        zip_bytes = fetcher.download_document(doc_id, doc_type=1)
        if zip_bytes:
            sections = parser.parse_zip(zip_bytes)
            if sections:
                metadata = {
                    "accessionNumber": doc_id,
                    "ticker": ticker,
                    "cik": edinet_code,
                    "form": "120",
                    "filingDate": found_doc.get("filingDate"),
                    "filerName": found_doc.get("filerName"),
                }
                
                async with jp_db_write_lock:
                    storage.save_filing(metadata, sections)

        time.sleep(0.5)
    except Exception as e:
        logger.error(f"Failed to process JP ticker {ticker}: {e}")


if __name__ == "__main__":
    import sys
    import argparse
    from src.logging_utils import setup_logging

    setup_logging("batch")
    
    parser = argparse.ArgumentParser(description="Financial Narratives Data Lake Ingestion")
    parser.add_argument("--days", type=int, default=7, help="Number of days to look back")
    parser.add_argument("--tickers", nargs="+", help="Specific tickers to fetch")
    
    args = parser.parse_args()

    asyncio.run(batch_fetch(tickers=args.tickers, days=args.days))