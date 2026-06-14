import asyncio
import gc
from datetime import date, timedelta

import requests
from loguru import logger

from .fetcher import EdgarFetcher
from .parser import EdgarParser
from .quantitative import EdgarQuantitative
# edgar_core will be available as a package
from edgar_core import EdgarStorage


async def sync_recent_us_filings(fetcher: EdgarFetcher, parser: EdgarParser, storage: EdgarStorage, days=7):
    """
    SEC Daily Index を使用して、指定された過去日数分の 10-K/Q 提出書類を同期する
    """
    today = date.today()

    for i in range(days):
        target_date = today - timedelta(days=i)
        logger.info(f"Syncing US filings via daily index | date={target_date}")

        try:
            # 1. 指定日のインデックスを取得
            filings = await asyncio.to_thread(fetcher.list_daily_filings, target_date)
            if not filings:
                continue

            for entry in filings:
                try:
                    acc_no = entry["accessionNumber"]
                    ticker = entry.get("ticker")

                    if not ticker or ticker == "UNKNOWN":
                        continue

                    # Smart Repair Logic
                    needs_full_sync = not storage.filing_exists(acc_no)
                    needs_facts_repair = not needs_full_sync and not storage.facts_exist(acc_no)

                    if not needs_full_sync and not needs_facts_repair:
                        continue

                    if needs_full_sync:
                        # 詳細なメタデータを解決
                        logger.info(f"Resolving metadata | ticker={ticker} | acc_no={acc_no}")
                        filing = await asyncio.to_thread(fetcher.resolve_filing_metadata, ticker, acc_no)
                        if not filing:
                            continue

                        # 書類をダウンロード
                        cik = entry["cik"].lstrip("0")
                        acc_no_clean = acc_no.replace("-", "")
                        doc_name = filing["primaryDocument"]
                        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_clean}/{doc_name}"

                        logger.info(f"Downloading | ticker={ticker} | acc_no={acc_no}")
                        resp = await asyncio.to_thread(requests.get, url, headers=fetcher.headers, timeout=30)
                        await asyncio.sleep(0.11)

                        if resp.status_code == 200:
                            # 定性データの保存
                            sections = parser.extract_all_sections(resp.text, filing["form"])
                            if sections:
                                filing_metadata = filing.copy()
                                filing_metadata["ticker"] = ticker
                                filing_metadata["cik"] = cik
                                storage.save_filing(filing_metadata, sections)
                        del resp

                    # 定量データの抽出・保存
                    logger.info(f"Syncing financial facts | ticker={ticker} | acc_no={acc_no}")
                    facts_df = await asyncio.to_thread(EdgarQuantitative.extract_facts, acc_no)
                    if not facts_df.empty:
                        storage.save_facts(ticker, acc_no, facts_df)

                    gc.collect()
                except Exception:
                    logger.exception(f"Error processing US filing | acc_no={acc_no}")
        except Exception:
            logger.exception(f"Failed to process US index | date={target_date}")


async def process_us_tickers(tickers, fetcher: EdgarFetcher, parser: EdgarParser, storage: EdgarStorage, days=365):
    """指定されたティッカーの直近書類を同期する"""
    for ticker in tickers:
        try:
            logger.info(f"Processing ticker | ticker={ticker}")
            subs = await asyncio.to_thread(fetcher.get_latest_submissions, ticker)
            if not subs:
                continue

            filings = fetcher.filter_relevant_filings(subs)
            if not filings:
                continue

            threshold_date = (date.today() - timedelta(days=days)).isoformat()
            target_filings = [f for f in filings if f["filingDate"] >= threshold_date]

            for filing in target_filings:
                acc_no = filing["accessionNumber"]
                
                needs_full_sync = not storage.filing_exists(acc_no)
                needs_facts_repair = not needs_full_sync and not storage.facts_exist(acc_no)

                if not needs_full_sync and not needs_facts_repair:
                    continue

                if needs_full_sync:
                    cik = fetcher.get_cik(ticker).lstrip("0")
                    acc_no_clean = acc_no.replace("-", "")
                    doc_name = filing["primaryDocument"]
                    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_clean}/{doc_name}"

                    logger.info(f"Downloading | ticker={ticker} | date={filing['filingDate']}")
                    resp = await asyncio.to_thread(requests.get, url, headers=fetcher.headers, timeout=30)
                    await asyncio.sleep(0.11)

                    if resp.status_code == 200:
                        sections = parser.extract_all_sections(resp.text, filing["form"])
                        if sections:
                            filing_metadata = filing.copy()
                            filing_metadata["ticker"] = ticker
                            filing_metadata["cik"] = cik
                            storage.save_filing(filing_metadata, sections)
                    del resp
                
                # 定量データの抽出
                logger.info(f"Syncing financial facts | ticker={ticker} | acc_no={acc_no}")
                facts_df = await asyncio.to_thread(EdgarQuantitative.extract_facts, acc_no)
                if not facts_df.empty:
                    storage.save_facts(ticker, acc_no, facts_df)
                
                gc.collect()
        except Exception:
            logger.exception(f"Failed to process ticker | ticker={ticker}")


async def repair_all_missing_facts(storage: EdgarStorage):
    """DBを走査し、数値データが欠けている全レコードを修復する"""
    targets = storage.get_accession_numbers_needing_repair()
    logger.info(f"Found {len(targets)} filings needing facts repair.")
    
    for acc_no, ticker in targets:
        try:
            logger.info(f"Repairing facts | ticker={ticker} | acc_no={acc_no}")
            facts_df = await asyncio.to_thread(EdgarQuantitative.extract_facts, acc_no)
            if not facts_df.empty:
                storage.save_facts(ticker, acc_no, facts_df)
            else:
                logger.warning(f"No facts found during repair for {acc_no}")
            
            await asyncio.sleep(0.1) 
            gc.collect()
        except Exception:
            logger.exception(f"Failed to repair facts for {acc_no}")
