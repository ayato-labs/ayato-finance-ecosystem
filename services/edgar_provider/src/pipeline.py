import asyncio
import os
from datetime import date, timedelta

from dotenv import load_dotenv
from loguru import logger

from .fetcher import EdgarFetcher
from .parser import EdgarParser
from .quantitative import EdgarQuantitative
from .storage import EdgarStorage

# .env ファイルから環境変数を読み込み
load_dotenv()

# バッチサイズ（.envファイルで設定可能）
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))


async def _download_and_buffer_filing(
    entry_or_filing: dict,
    ticker: str,
    acc_no: str,
    filing_date: str,
    cik: str,
    fetcher: EdgarFetcher,
    parser: EdgarParser,
    storage: EdgarStorage,
    filings_buffer: list[tuple[dict, dict]],
):
    """HTML本文をダウンロードおよびパースし、filings_bufferに格納します。必要に応じてバッチ保存を実行します。"""
    filing = await asyncio.to_thread(fetcher.resolve_filing_metadata, ticker, acc_no)
    if not filing:
        return

    doc_name = filing["primaryDocument"]

    logger.info(
        f"Downloading | ticker={ticker} | acc_no={acc_no} | filing_date={filing_date} | form={entry_or_filing.get('form', 'unknown')}"
    )
    content = await asyncio.to_thread(fetcher.fetch_filing_content, cik, acc_no, doc_name)
    await asyncio.sleep(0.11)

    if content:
        sections = parser.extract_all_sections(content, filing["form"])
        if sections:
            filing_metadata = filing.copy()
            filing_metadata["ticker"] = ticker
            filing_metadata["cik"] = cik
            filings_buffer.append((filing_metadata, sections))

            if len(filings_buffer) >= BATCH_SIZE:
                logger.info(f"Flushing filings buffer | count={len(filings_buffer)} | ticker={ticker}")
                storage.save_filings_batch(filings_buffer)
                filings_buffer.clear()


async def _extract_and_buffer_facts(
    ticker: str,
    acc_no: str,
    filing_date: str,
    needs_facts_repair: bool,
    storage: EdgarStorage,
    facts_buffer: list[tuple[str, str, any]],
):
    """財務数値Factsデータを抽出し、facts_bufferに格納します。必要に応じてバッチ保存を実行します。"""
    if needs_facts_repair:
        logger.info(f"Repairing facts | ticker={ticker} | acc_no={acc_no} | filing_date={filing_date}")
    else:
        logger.debug(f"Syncing financial facts | ticker={ticker} | acc_no={acc_no} | filing_date={filing_date}")

    facts_df = await asyncio.to_thread(EdgarQuantitative.extract_facts, acc_no)
    if not facts_df.empty:
        facts_buffer.append((ticker, acc_no, facts_df))
        if len(facts_buffer) >= BATCH_SIZE:
            logger.info(f"Flushing facts buffer | count={len(facts_buffer)} | ticker={ticker}")
            storage.save_facts_batch(facts_buffer)
            facts_buffer.clear()


async def sync_recent_us_filings(
    fetcher: EdgarFetcher, parser: EdgarParser, storage: EdgarStorage, days=7
):
    """
    SEC Daily Index（日次インデックス一覧）を使用して、
    米国上場企業全体の指定過去日数分の提出書類（10-K, 10-Q）を同期・収集します。
    """
    today = date.today()
    threshold_date = (today - timedelta(days=days)).isoformat()

    filings_buffer: list[tuple[dict, dict]] = []
    facts_buffer: list[tuple[str, str, any]] = []

    logger.info(f"Starting sync | days={days} | threshold_date={threshold_date}")

    for i in range(days):
        target_date = today - timedelta(days=i)
        daily_skipped = 0
        daily_processed = 0
        logger.info(f"Syncing US filings via daily index | date={target_date}")

        try:
            filings = await asyncio.to_thread(fetcher.list_daily_filings, target_date)
            if not filings:
                logger.debug(f"No filings found for date (weekend/holiday) | date={target_date}")
                continue

            logger.info(f"Found filings in daily index | date={target_date} | count={len(filings)}")
            skipped_tickers = []

            for entry in filings:
                try:
                    acc_no = entry["accessionNumber"]
                    ticker = entry.get("ticker", "UNKNOWN")
                    filing_date = entry.get("filingDate", "unknown")

                    if ticker == "UNKNOWN":
                        logger.debug(f"Skipping unknown ticker | acc_no={acc_no}")
                        continue

                    needs_full_sync = not storage.filing_exists(acc_no)
                    needs_facts_repair = not needs_full_sync and not storage.facts_exist(acc_no)

                    if not needs_full_sync and not needs_facts_repair:
                        daily_skipped += 1
                        skipped_tickers.append(f"{ticker} ({filing_date})")
                        logger.info(
                            f"Skipping (already synced) | ticker={ticker} | acc_no={acc_no} | filing_date={filing_date}"
                        )
                        continue

                    if needs_full_sync:
                        cik = entry["cik"].lstrip("0")
                        await _download_and_buffer_filing(
                            entry, ticker, acc_no, filing_date, cik, fetcher, parser, storage, filings_buffer
                        )

                    await _extract_and_buffer_facts(
                        ticker, acc_no, filing_date, needs_facts_repair, storage, facts_buffer
                    )
                    daily_processed += 1

                except Exception:
                    logger.exception(f"Error processing US filing | acc_no={acc_no} | filing_date={filing_date}")

            logger.info(
                f"Completed daily sync | date={target_date} | processed={daily_processed} | skipped={daily_skipped}"
            )
            if skipped_tickers:
                logger.info(
                    f"Skipped tickers (already synced) | date={target_date} | count={len(skipped_tickers)} | tickers={', '.join(skipped_tickers[:10])}{'...' if len(skipped_tickers) > 10 else ''}"
                )
        except Exception:
            logger.exception(f"Failed to process US index | date={target_date}")

    if filings_buffer:
        logger.info(f"Flushing final filings buffer | count={len(filings_buffer)}")
        storage.save_filings_batch(filings_buffer)

    if facts_buffer:
        logger.info(f"Flushing final facts buffer | count={len(facts_buffer)}")
        storage.save_facts_batch(facts_buffer)

    logger.info("Sync completed")


async def process_us_tickers(
    tickers, fetcher: EdgarFetcher, parser: EdgarParser, storage: EdgarStorage, days=365
):
    """
    指定された特定のティッカーシンボル群（個別指定）について、
    直近指定日数分の提出書類をピンポイントで同期・収集します。
    """
    filings_buffer: list[tuple[dict, dict]] = []
    facts_buffer: list[tuple[str, str, any]] = []

    threshold_date = (date.today() - timedelta(days=days)).isoformat()
    logger.info(f"Processing tickers | count={len(tickers)} | threshold_date={threshold_date}")

    for ticker in tickers:
        skipped_count = 0
        processed_count = 0
        try:
            logger.info(f"Processing ticker | ticker={ticker}")
            subs = await asyncio.to_thread(fetcher.get_latest_submissions, ticker)
            if not subs:
                logger.warning(f"No submissions found | ticker={ticker}")
                continue

            filings = fetcher.filter_relevant_filings(subs)
            if not filings:
                logger.warning(f"No 10-K/10-Q filings found | ticker={ticker}")
                continue

            target_filings = [f for f in filings if f["filingDate"] >= threshold_date]
            logger.info(
                f"Found filings | ticker={ticker} | total={len(filings)} | "
                f"in_range={len(target_filings)} | threshold={threshold_date}"
            )

            skipped_filings = []
            skipped_facts = []

            for filing in target_filings:
                acc_no = filing["accessionNumber"]
                filing_date = filing.get("filingDate", "unknown")

                needs_full_sync = not storage.filing_exists(acc_no)
                needs_facts_repair = not needs_full_sync and not storage.facts_exist(acc_no)

                if not needs_full_sync and not needs_facts_repair:
                    skipped_count += 1
                    skipped_filings.append(f"{filing_date} ({acc_no})")
                    logger.info(
                        f"Skipping (already synced) | ticker={ticker} | acc_no={acc_no} | filing_date={filing_date}"
                    )
                    continue

                if needs_facts_repair:
                    skipped_facts.append(f"{filing_date} ({acc_no})")

                if needs_full_sync:
                    cik = fetcher.get_cik(ticker).lstrip("0")
                    await _download_and_buffer_filing(
                        filing, ticker, acc_no, filing_date, cik, fetcher, parser, storage, filings_buffer
                    )

                await _extract_and_buffer_facts(
                    ticker, acc_no, filing_date, needs_facts_repair, storage, facts_buffer
                )
                processed_count += 1

            logger.info(
                f"Completed ticker | ticker={ticker} | processed={processed_count} | skipped={skipped_count}"
            )
            if skipped_filings:
                logger.info(
                    f"Skipped filings (already synced) | ticker={ticker} | count={len(skipped_filings)} | dates={', '.join(skipped_filings[:5])}{'...' if len(skipped_filings) > 5 else ''}"
                )
            if skipped_facts:
                logger.info(
                    f"Skipped facts (repair needed) | ticker={ticker} | count={len(skipped_facts)} | dates={', '.join(skipped_facts[:5])}{'...' if len(skipped_facts) > 5 else ''}"
                )
        except Exception:
            logger.exception(f"Failed to process ticker | ticker={ticker}")

    if filings_buffer:
        logger.info(f"Flushing final filings buffer | count={len(filings_buffer)}")
        storage.save_filings_batch(filings_buffer)

    if facts_buffer:
        logger.info(f"Flushing final facts buffer | count={len(facts_buffer)}")
        storage.save_facts_batch(facts_buffer)


async def repair_all_missing_facts(storage: EdgarStorage):
    """
    データ整合性の「自己修復（リペア）」バッチ。
    データベース内の全レコードを走査し、定性データ（報告書本文）はあるが
    定量数値データ（Facts）が欠落しているレコードを検出して、自動的にXBRLデータを再抽出し修復します。
    """
    targets = storage.get_accession_numbers_needing_repair()
    logger.info(f"Found {len(targets)} filings needing facts repair.")

    # バッチ処理用のバッファ
    facts_buffer: list[tuple[str, str, any]] = []

    for acc_no, ticker in targets:
        try:
            logger.info(f"Repairing facts | ticker={ticker} | acc_no={acc_no}")
            facts_df = await asyncio.to_thread(EdgarQuantitative.extract_facts, acc_no)
            if not facts_df.empty:
                facts_buffer.append((ticker, acc_no, facts_df))

                # バッチサイズに達したら一括書き込み
                if len(facts_buffer) >= BATCH_SIZE:
                    logger.info(f"Flushing facts buffer | count={len(facts_buffer)}")
                    storage.save_facts_batch(facts_buffer)
                    facts_buffer.clear()
            else:
                logger.warning(f"No facts found during repair for {acc_no}")

            await asyncio.sleep(0.1)
        except Exception:
            logger.exception(f"Failed to repair facts for {acc_no}")

    # 残りのバッファを一括書き込み
    if facts_buffer:
        logger.info(f"Flushing final facts buffer | count={len(facts_buffer)}")
        storage.save_facts_batch(facts_buffer)
