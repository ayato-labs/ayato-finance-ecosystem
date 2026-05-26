import asyncio
import gc
import os
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from loguru import logger

from src.config import SEC_TICKERS, USER_AGENT
from src.edgar_fetcher import EdgarFetcher
from src.edgar_parser import EdgarParser
from src.edinet_fetcher import EdinetFetcher
from src.edinet_parser import EdinetParser
from src.storage import FinancialNarrativeStorage

# デフォルト銘柄リスト
TICKERS = ["AAPL", "NVDA", "7203", "9984"]


async def batch_fetch(
    tickers: list[str] | None = None, run_structuring: bool = False, days: int = 7
):
    """
    日米市場の定性データを一括取得・構造化保存する。
    """
    logger.info(
        f"Starting batch_fetch | tickers_specified={tickers is not None} | "
        f"run_structuring={run_structuring} | days={days}"
    )

    storage = FinancialNarrativeStorage()
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
                        await process_jp_ticker(
                            ticker, edinet_fetcher, edinet_parser, storage, run_structuring
                        )
                    else:
                        await process_us_ticker(
                            ticker, edgar_fetcher, edgar_parser, storage, run_structuring, days=3650
                        )
                    gc.collect()
                except Exception:
                    logger.exception(f"Unexpected error processing ticker | ticker={ticker}")
        else:
            # 2. 自動同期 (全上場企業対象)
            logger.info(f"Starting automated parallel sync | lookback_days={days}")

            # 日米の市場を並列で同期する (専門家の提言: レート制限は市場ごとに独立しているため)
            # asyncio.gather により、JPとUSのパイプラインを同時に走らせる
            tasks = [
                sync_recent_jp_filings(
                    edinet_fetcher,
                    edinet_parser,
                    storage,
                    days=days,
                    run_structuring=run_structuring,
                ),
                sync_recent_us_filings(
                    edgar_fetcher, edgar_parser, storage, days=days, run_structuring=run_structuring
                ),
            ]

            try:
                await asyncio.gather(*tasks)
            except Exception:
                logger.exception("Global failure during parallel market synchronization")

    except Exception:
        logger.exception("Critical error in batch_fetch orchestration")
    finally:
        logger.info("Batch fetch orchestration completed")


async def sync_recent_jp_filings(fetcher, parser, storage, days=7, run_structuring=False):
    """EDINETの書類一覧APIを使用して、指定日数の全上場企業の開示を同期"""
    today = date.today()

    for i in range(days):
        target_date = today - timedelta(days=i)
        logger.info(f"Syncing JP filings | date={target_date}")

        try:
            docs = await asyncio.to_thread(fetcher.list_documents, target_date)
            # 有報(120), 四半期(140) 等を抽出
            target_forms = ["120", "140"]
            relevant_docs = [d for d in docs if d.get("docTypeCode") in target_forms]

            for doc in relevant_docs:
                try:
                    doc_id = doc["docID"]
                    ticker = (doc.get("secCode") or "")[:4]
                    if not ticker or storage.filing_exists(doc_id):
                        continue

                    logger.info(f"Downloading JP filing | ticker={ticker} | doc_id={doc_id}")
                    # ブロッキングなI/Oを別スレッドで実行
                    zip_bytes = await asyncio.to_thread(
                        fetcher.download_document, doc_id, doc_type=1
                    )
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
                            if run_structuring:
                                await run_structuring_for_filing(ticker, doc_id, sections, storage)
                    del zip_bytes
                    gc.collect()
                    # 非同期スリープにより他タスクに制御を譲る
                    await asyncio.sleep(0.1)
                except Exception:
                    logger.exception(f"Error processing JP document | doc_id={doc.get('docID')}")
        except Exception:
            logger.exception(f"Failed to fetch JP document list | date={target_date}")


async def sync_recent_us_filings(fetcher, parser, storage, days=7, run_structuring=False):
    """SEC Daily Index を使用して、指定期間内の全米国上場企業の開示を同期"""
    today = date.today()

    for i in range(days):
        target_date = today - timedelta(days=i)
        logger.info(f"Syncing US filings via daily index | date={target_date}")

        try:
            # 1. 指定日の全 10-K/Q 提出書類をインデックスから一括取得
            filings = await asyncio.to_thread(fetcher.list_daily_filings, target_date)
            if not filings:
                continue

            for entry in filings:
                try:
                    acc_no = entry["accessionNumber"]
                    ticker = entry.get("ticker")

                    # 2. 既に取得済みかチェック
                    if storage.filing_exists(acc_no):
                        continue

                    # ティッカーが不明な場合はスキップ (マスターリストにない銘柄)
                    if not ticker or ticker == "UNKNOWN":
                        logger.debug(f"Skipping unknown ticker for CIK {entry['cik']}")
                        continue

                    # 3. 正確なメタデータ（特に primaryDocument のファイル名）を解決
                    logger.info(f"Resolving metadata | ticker={ticker} | acc_no={acc_no}")
                    filing = await asyncio.to_thread(fetcher.resolve_filing_metadata, ticker, acc_no)
                    if not filing:
                        logger.warning(f"Could not resolve metadata for {acc_no}")
                        continue

                    # 4. ダウンロード実行 (正確な HTML ファイルを取得)
                    cik = entry["cik"].lstrip("0")
                    acc_no_clean = acc_no.replace("-", "")
                    doc_name = filing["primaryDocument"]
                    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_clean}/{doc_name}"

                    logger.info(
                        f"Downloading US filing | ticker={ticker} | acc_no={acc_no} | "
                        f"doc={doc_name}"
                    )
                    resp = await asyncio.to_thread(
                        requests.get, url, headers=fetcher.headers, timeout=30
                    )
                    # SEC Rate Limit (10 requests/second) を遵守
                    await asyncio.sleep(0.11)

                    if resp.status_code != 200:
                        logger.error(
                            f"Failed to download US filing | ticker={ticker} | status={resp.status_code}"
                        )
                        continue

                    # 5. パースと保存
                    sections = parser.extract_all_sections(resp.text, filing["form"])
                    if sections:
                        filing_metadata = filing.copy()
                        filing_metadata["ticker"] = ticker
                        filing_metadata["cik"] = cik
                        storage.save_filing(filing_metadata, sections)
                        if run_structuring:
                            await run_structuring_for_filing(ticker, acc_no, sections, storage)

                    del resp
                    gc.collect()
                except Exception:
                    logger.exception(
                        f"Error processing US filing | acc_no={entry.get('accessionNumber')}"
                    )
        except Exception:
            logger.exception(f"Failed to process US index | date={target_date}")


async def process_us_ticker(ticker, fetcher, parser, storage, run_structuring=False, days=7):
    """指定期間内の SEC EDGAR 提出書類を処理"""
    try:
        # 1. 提出書類リスト取得 (ブロッキング回避)
        subs = await asyncio.to_thread(fetcher.get_latest_submissions, ticker)
        if not subs:
            return

        # 2. 指定期間内の 10-K/Q を抽出
        filings = fetcher.filter_relevant_filings(subs, doc_types=["10-K", "10-Q"])
        if not filings:
            return

        # 期間フィルター
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

                # 3. ダウンロード (ブロッキングI/Oを回避)
                logger.info(
                    f"Downloading US filing | ticker={ticker} | acc_no={acc_no} | "
                    f"date={filing['filingDate']}"
                )
                resp = await asyncio.to_thread(
                    requests.get, url, headers=fetcher.headers, timeout=30
                )
                await asyncio.sleep(0.1)

                if resp.status_code != 200:
                    logger.error(
                        f"Failed to download US filing | ticker={ticker} | status={resp.status_code}"
                    )
                    continue

                # 4. パース
                sections = parser.extract_all_sections(resp.text, filing["form"])
                if sections:
                    filing_metadata = filing.copy()
                    filing_metadata["ticker"] = ticker
                    filing_metadata["cik"] = cik
                    storage.save_filing(filing_metadata, sections)
                    if run_structuring:
                        await run_structuring_for_filing(ticker, acc_no, sections, storage)

                del resp
                gc.collect()
            except Exception:
                logger.exception(
                    f"Error processing US filing | ticker={ticker} | acc_no={filing.get('accessionNumber')}"
                )

    except Exception:
        logger.exception(f"Failed to process US ticker | ticker={ticker}")


async def process_jp_ticker(ticker, fetcher, parser, storage, run_structuring=False):
    """Process EDINET for JP tickers (On-demand)."""
    try:
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
                if run_structuring:
                    await run_structuring_for_filing(ticker, doc_id, sections, storage)

        time.sleep(0.5)
    except Exception as e:
        logger.error(f"Failed to process JP ticker {ticker}: {e}")


async def run_structuring_for_filing(ticker, acc_no, sections, storage):
    """AIによる高度な事実抽出（構造化）を実行し保存する"""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("GOOGLE_API_KEY not set, skipping structuring.")
        return

    # すでに構造化済みかチェック
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
    import argparse
    from src.core.logging import setup_logger

    setup_logger(log_dir="logs", app_name="financial_narratives_sync")

    parser = argparse.ArgumentParser(description="Financial Narratives Batch Fetcher")
    parser.add_argument("--days", type=int, default=7, help="Number of days to look back")
    parser.add_argument("--tickers", nargs="+", help="Specific tickers to fetch")
    parser.add_argument("--structure", action="store_true", help="Run AI structuring after fetch")

    args = parser.parse_args()

    asyncio.run(batch_fetch(tickers=args.tickers, run_structuring=args.structure, days=args.days))
