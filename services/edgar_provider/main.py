import asyncio
import gc
import os
from datetime import date, timedelta

import requests
from loguru import logger

from src.core.logging import setup_logger
from src.edgar_fetcher import EdgarFetcher
from src.edgar_parser import EdgarParser
from src.storage import EdgarStorage


async def sync_recent_us_filings(fetcher, parser, storage, days=7):
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

                    # 2. 既に存在するか確認
                    if storage.filing_exists(acc_no):
                        continue

                    # ティッカー不明はスキップ
                    if not ticker or ticker == "UNKNOWN":
                        logger.debug(f"Skipping unknown ticker for CIK {entry['cik']}")
                        continue

                    # 3. 詳細なメタデータを解決 (Primary Document 名等)
                    logger.info(f"Resolving metadata | ticker={ticker} | acc_no={acc_no}")
                    filing = await asyncio.to_thread(fetcher.resolve_filing_metadata, ticker, acc_no)
                    if not filing:
                        logger.warning(f"Could not resolve metadata for {acc_no}")
                        continue

                    # 4. 書類をダウンロード
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
                    # SECの規約(10 req/s)を守るための待機
                    await asyncio.sleep(0.11)

                    if resp.status_code != 200:
                        logger.error(
                            f"Failed to download | ticker={ticker} | status={resp.status_code}"
                        )
                        continue

                    # 5. パースして保存
                    sections = parser.extract_all_sections(resp.text, filing["form"])
                    if sections:
                        filing_metadata = filing.copy()
                        filing_metadata["ticker"] = ticker
                        filing_metadata["cik"] = cik
                        storage.save_filing(filing_metadata, sections)

                    del resp
                    gc.collect()
                except Exception:
                    logger.exception(
                        f"Error processing US filing | acc_no={entry.get('accessionNumber')}"
                    )
        except Exception:
            logger.exception(f"Failed to process US index | date={target_date}")


async def process_us_tickers(tickers, fetcher, parser, storage, days=365):
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
                if storage.filing_exists(acc_no):
                    continue

                cik = fetcher.get_cik(ticker).lstrip("0")
                acc_no_clean = acc_no.replace("-", "")
                doc_name = filing["primaryDocument"]
                url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_clean}/{doc_name}"

                logger.info(f"Downloading | ticker={ticker} | date={filing['filingDate']}")
                resp = await asyncio.to_thread(
                    requests.get, url, headers=fetcher.headers, timeout=30
                )
                await asyncio.sleep(0.11)

                if resp.status_code == 200:
                    sections = parser.extract_all_sections(resp.text, filing["form"])
                    if sections:
                        filing_metadata = filing.copy()
                        filing_metadata["ticker"] = ticker
                        filing_metadata["cik"] = cik
                        storage.save_filing(filing_metadata, sections)
                
                del resp
                gc.collect()
        except Exception:
            logger.exception(f"Failed to process ticker | ticker={ticker}")


def main():
    import argparse

    setup_logger(log_dir="logs", app_name="edgar_provider")

    parser = argparse.ArgumentParser(description="SEC EDGAR Provider CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Sync command
    sync_parser = subparsers.add_parser("sync", help="Sync filings from daily index")
    sync_parser.add_argument("--days", type=int, default=1, help="Number of days to look back")

    # Ticker command
    ticker_parser = subparsers.add_parser("ticker", help="Sync filings for specific tickers")
    ticker_parser.add_argument("tickers", nargs="+", help="Tickers to sync")
    ticker_parser.add_argument("--days", type=int, default=365, help="History depth in days")

    # Stats command
    subparsers.add_parser("stats", help="Show database statistics")

    args = parser.parse_args()

    user_agent = os.environ.get(
        "USER_AGENT", "edgar-provider/1.0 (contact: admin@example.com)"
    )
    fetcher = EdgarFetcher(user_agent=user_agent)
    parser_obj = EdgarParser()
    storage = EdgarStorage()

    if args.command == "sync":
        asyncio.run(sync_recent_us_filings(fetcher, parser_obj, storage, days=args.days))
    elif args.command == "ticker":
        asyncio.run(process_us_tickers(args.tickers, fetcher, parser_obj, storage, days=args.days))
    elif args.command == "stats":
        stats = storage.get_stats()
        print(f"Total filings: {stats['total_filings']}")
        for s in stats["ticker_stats"]:
            print(f"- {s['ticker']}: {s['count']} filings (Latest: {s['latest_filing']})")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
