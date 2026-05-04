import asyncio
import gc
import os
import time
from datetime import date, timedelta

import requests
from loguru import logger

from src.edgar_fetcher import EdgarFetcher
from src.edgar_parser import EdgarParser
from src.edinet_fetcher import EdinetFetcher
from src.edinet_parser import EdinetParser
from src.logging_utils import log_memory_usage
from src.storage import FinancialNarrativeStorage

USER_AGENT = "SampleAgent yourname@example.com"
TICKERS = ["AAPL", "NVDA", "7203", "9984"]  # 日米混在例


async def batch_fetch(tickers: list[str] = None, run_analysis: bool = False):
    """
    日米市場の定性データを一括取得・構造化保存する。

    tickers が指定された場合: 指定銘柄をオンデマンドで取得。
    tickers が None の場合: EDINET/SECの最新開示を監視し、全上場企業を対象に差分同期。
    run_analysis が True の場合: 取得後にAIによる分析を実行。
    """
    storage = FinancialNarrativeStorage()
    edgar_fetcher = EdgarFetcher(USER_AGENT)
    edgar_parser = EdgarParser()
    edinet_fetcher = EdinetFetcher()
    edinet_parser = EdinetParser()

    if tickers:
        # 1. 特定銘柄のオンデマンド処理
        for ticker in tickers:
            try:
                logger.info(f"=== Processing {ticker} (On-demand) ===")
                is_jp = ticker.isdigit()
                if is_jp:
                    await process_jp_ticker(
                        ticker, edinet_fetcher, edinet_parser, storage, run_analysis
                    )
                else:
                    await process_us_ticker(
                        ticker, edgar_fetcher, edgar_parser, storage, run_analysis
                    )

                # RAM使用効率向上
                gc.collect()
                log_memory_usage(f"On-demand: {ticker}")
            except Exception as e:
                logger.error(f"Error processing {ticker}: {e}")
    else:
        # 2. 最新開示ベースの自動同期 (全上場企業対象)
        logger.info("=== Starting Automated Sync for All Listed Companies ===")
        await sync_recent_jp_filings(edinet_fetcher, edinet_parser, storage, run_analysis=run_analysis)
        await sync_recent_us_filings(
            edgar_fetcher, edgar_parser, storage, run_analysis=run_analysis
        )


async def sync_recent_jp_filings(fetcher, parser, storage, days=7, run_analysis=False):
    """EDINETの書類一覧APIを使用して、直近N日間の全上場企業の開示を同期"""
    today = date.today()

    for i in range(days):
        target_date = today - timedelta(days=i)
        docs = fetcher.list_documents(target_date)

        # 有報(120), 四半期(140) 等を抽出
        target_forms = ["120", "140"]
        relevant_docs = [d for d in docs if d.get("docTypeCode") in target_forms]

        logger.info(f"Found {len(relevant_docs)} relevant filings on {target_date}")

        for doc in relevant_docs:
            doc_id = doc["docID"]
            ticker = (doc.get("secCode") or "")[:4]  # 証券コード4桁
            if not ticker:
                continue

            if storage.filing_exists(doc_id):
                continue

            logger.info(f"Syncing JP filing: {ticker} ({doc_id})")
            zip_bytes = fetcher.download_document(doc_id, doc_type=1)
            if zip_bytes:
                sections = parser.parse_zip(zip_bytes)
                if sections:
                    metadata = {
                        "accessionNumber": doc_id,
                        "ticker": ticker,
                        "cik": doc.get("edinetCode"),
                        "form": doc.get("formCode"),
                        "filingDate": doc.get("filingDate"),
                        "filerName": doc.get("filerName"),
                    }
                    storage.save_filing(metadata, sections)
                    if run_analysis:
                        await run_analysis_for_filing(ticker, doc_id, sections, storage)

            # RAM使用効率向上のためメモリ解放を明示
            del zip_bytes
            gc.collect()
            log_memory_usage(f"JP Sync: {ticker}")
            time.sleep(0.1)


async def sync_recent_us_filings(fetcher, parser, storage, run_analysis=False):
    """SECの最新提出書類(RSS等)から同期 (現在は主要銘柄の最新を確認する簡易版)"""
    # TODO: SECの全銘柄同期は index.idx 等を使用するのが一般的
    default_tickers = ["AAPL", "NVDA", "GOOGL", "AMZN", "META", "MSFT", "TSLA"]
    for ticker in default_tickers:
        await process_us_ticker(ticker, fetcher, parser, storage, run_analysis)


async def process_us_ticker(ticker, fetcher, parser, storage, run_analysis=False):
    """Process SEC EDGAR for US tickers."""
    # 1. 提出書類リスト取得
    subs = fetcher.get_latest_submissions(ticker)
    if not subs:
        return

    # 2. 最新10-K特定
    filings = fetcher.filter_relevant_filings(subs, doc_types=["10-K", "10-Q"])
    if not filings:
        return

    latest = filings[0]
    acc_no = latest["accessionNumber"]

    if storage.filing_exists(acc_no):
        return

    cik = fetcher.get_cik(ticker).lstrip("0")
    acc_no_clean = acc_no.replace("-", "")
    doc = latest["primaryDocument"]
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_clean}/{doc}"

    # 3. ダウンロード
    logger.info(f"Downloading US filing: {ticker} ({acc_no})")
    resp = requests.get(url, headers={"User-Agent": USER_AGENT})
    time.sleep(0.1)

    if resp.status_code != 200:
        return

    # 4. パース
    sections = parser.extract_all_sections(resp.text, latest["form"])
    if sections:
        filing_metadata = latest.copy()
        filing_metadata["ticker"] = ticker
        filing_metadata["cik"] = cik
        storage.save_filing(filing_metadata, sections)
        if run_analysis:
            await run_analysis_for_filing(ticker, acc_no, sections, storage)

    # RAM使用効率向上
    del resp
    gc.collect()
    log_memory_usage(f"US Process: {ticker}")
    time.sleep(0.5)


async def process_jp_ticker(ticker, fetcher, parser, storage, run_analysis=False):
    """Process EDINET for JP tickers (On-demand)."""
    edinet_code = fetcher.get_edinet_code(ticker)
    if not edinet_code:
        logger.warning(f"EDINET Code not found for ticker {ticker}")
        return

    today = date.today()
    found_doc = None
    # 過去1年分を遡って最新の有報を探す
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
        logger.warning(f"No recent Yuho found for {ticker}")
        return

    doc_id = found_doc["docID"]
    if storage.filing_exists(doc_id):
        logger.info(f"Filing {doc_id} already exists in DB.")
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
            storage.save_filing(metadata, sections)
            if run_analysis:
                await run_analysis_for_filing(ticker, doc_id, sections, storage)

    time.sleep(0.5)


async def run_analysis_for_filing(ticker, acc_no, sections, storage):
    """AIによる感情・戦略分析を実行し保存する"""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("GOOGLE_API_KEY not set, skipping analysis.")
        return

    # すでに分析済みかチェック
    existing_analysis = storage.get_analysis_by_ticker(ticker)
    if existing_analysis:
        logger.info(f"Analysis already exists for {ticker}. Skipping.")
        return

    try:
        from src.analyzer import EdgarAnalyzer
        analyzer = EdgarAnalyzer(api_key=api_key)
        analysis = await analyzer.analyze_narratives(sections)
        if analysis:
            storage.save_analysis(acc_no, ticker, analysis)
            logger.info(f"Analysis saved for {ticker} ({acc_no})")
    except Exception as e:
        logger.error(f"Failed to analyze {ticker}: {e}")


if __name__ == "__main__":
    from src.logging_utils import setup_logging

    setup_logging("batch")
    asyncio.run(batch_fetch())
