import asyncio
import gc
import time
from datetime import date, timedelta

import requests
from dotenv import load_dotenv
from loguru import logger

from src.config import USER_AGENT
from src.db.master_db import JobQueue
from src.edgar_fetcher import EdgarFetcher
from src.edgar_parser import EdgarParser
from src.edinet_fetcher import EdinetFetcher
from src.edinet_parser import EdinetParser
from src.storage import FinancialNarrativeStorage

# .envファイルをロード
load_dotenv()


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
    logger.info(
        f"Starting batch_fetch (Ingestion Only) | "
        f"tickers_specified={tickers is not None} | days={days}"
    )

    storage_jp = FinancialNarrativeStorage(market="jp")
    storage_us = FinancialNarrativeStorage(market="us")
    edgar_fetcher = EdgarFetcher(USER_AGENT)
    edgar_parser = EdgarParser()
    edinet_fetcher = EdinetFetcher()
    edinet_parser = EdinetParser()
    queue = JobQueue()

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
                        await process_us_ticker(
                            ticker, edgar_fetcher, edgar_parser, storage_us, queue, days=3650
                        )
                    gc.collect()
                except Exception:
                    logger.exception(f"Unexpected error processing ticker | ticker={ticker}")
        else:
            # 2. 自動同期 (全上場企業対象)
            logger.info(f"Starting automated parallel sync | lookback_days={days}")

            tasks = [
                sync_recent_jp_filings(edinet_fetcher, edinet_parser, storage_jp, queue, days=days),
                sync_recent_us_filings(edgar_fetcher, edgar_parser, storage_us, queue, days=days)
            ]

            try:
                await asyncio.gather(*tasks)
            except Exception:
                logger.exception("Global failure during parallel market synchronization")

    except Exception:
        logger.exception("Critical error in batch_fetch orchestration")


async def sync_recent_jp_filings(fetcher, parser, storage, queue, days=7):
    """JP市場の書類を同期する"""
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

                logger.info(
                    f"Downloading JP filing | filer={doc.get('filerName')} | doc_id={doc_id}"
                )
                zip_bytes = await asyncio.to_thread(fetcher.download_document, doc_id, doc_type=1)

                if zip_bytes:
                    sections = await asyncio.to_thread(parser.parse_zip, zip_bytes)
                    if sections:
                        # EDINET API v2 uses submitDateTime (e.g. "2024-05-01 10:00")
                        submit_dt = doc.get("submitDateTime")
                        filing_date = submit_dt.split(" ")[0] if submit_dt else None

                        metadata = {
                            "accessionNumber": doc_id,
                            "ticker": ticker,
                            "cik": doc.get("edinetCode"),
                            "form": doc.get("formCode") or "UNKNOWN",
                            "filingDate": filing_date,
                            "filerName": doc.get("filerName"),
                        }
                        async with jp_db_write_lock:
                            await asyncio.to_thread(storage.save_filing, metadata, sections)

                        # 即座にジョブキューに登録 (構造化ワーカーへの通知)
                        await asyncio.to_thread(queue.enqueue_job, doc_id, ticker, "jp")

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


async def sync_recent_us_filings(fetcher, parser, storage, queue, days=7):
    """SEC Daily Index (RSS) を利用して、US市場の書類を高速に同期する。"""
    try:
        logger.info(f"Scanning US daily indices for the last {days} days...")
        recent_filings = await asyncio.to_thread(fetcher.get_recent_filings_from_index, days=days)

        if not recent_filings:
            logger.info("No new US filings found in index.")
            return

        for filing in recent_filings:
            try:
                acc_no = filing["accessionNumber"]
                if storage.filing_exists(acc_no):
                    continue

                # 詳細情報の取得と保存
                await download_and_save_us_filing(filing, fetcher, parser, storage, queue)
                await asyncio.sleep(0.1)  # SEC Rate Limit 配慮
            except Exception:
                logger.exception(
                    f"Error processing US filing from index | acc_no={filing.get('accessionNumber')}"
                )

    except Exception:
        logger.exception("Critical failure during index-based US synchronization")


async def download_and_save_us_filing(filing, fetcher, parser, storage, queue):
    """個別書類のダウンロード、パース、保存、およびジョブ登録を行う"""
    ticker = filing["ticker"]
    acc_no = filing["accessionNumber"]
    cik = filing["cik"]
    acc_no_clean = acc_no.replace("-", "")
    doc_name = filing["primaryDocument"]

    # URLの組み立て
    url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{acc_no_clean}/{doc_name}"

    logger.info(f"Downloading US filing | ticker={ticker} | acc_no={acc_no}")
    resp = await asyncio.to_thread(requests.get, url, headers=fetcher.headers, timeout=30)

    if resp.status_code != 200:
        logger.warning(f"Failed to download filing | status={resp.status_code} | url={url}")
        return

    sections = await asyncio.to_thread(parser.extract_all_sections, resp.text, filing["form"])
    if sections:
        filing_metadata = filing.copy()
        async with us_db_write_lock:
            await asyncio.to_thread(storage.save_filing, filing_metadata, sections)

        # 即座にジョブキューに登録
        await asyncio.to_thread(queue.enqueue_job, acc_no, ticker, "us")

    del resp
    gc.collect()


async def process_us_ticker(ticker, fetcher, parser, storage, queue, days=7):
    """特定US銘柄の処理"""
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

                filing["cik"] = fetcher.get_cik(ticker).lstrip("0")
                await download_and_save_us_filing(filing, fetcher, parser, storage, queue)
                await asyncio.sleep(0.1)
            except Exception:
                logger.exception(
                    f"Error processing US ticker filing | "
                    f"ticker={ticker} | acc_no={filing.get('accessionNumber')}"
                )

    except Exception:
        logger.exception(f"Failed to process US ticker | ticker={ticker}")


async def process_jp_ticker(ticker, fetcher, parser, storage):
    """特定JP銘柄の処理"""
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
    import argparse

    from src.logging_utils import setup_logging

    setup_logging("batch")

    arg_parser = argparse.ArgumentParser(description="Financial Narratives Data Lake Ingestion")
    arg_parser.add_argument("--days", type=int, default=7, help="Number of days to look back")
    arg_parser.add_argument("--tickers", nargs="+", help="Specific tickers to fetch")

    args = arg_parser.parse_args()

    asyncio.run(batch_fetch(tickers=args.tickers, days=args.days))
