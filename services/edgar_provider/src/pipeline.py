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


async def _filings_db_consumer(storage: EdgarStorage, queue: asyncio.Queue):
    """バックグラウンドで Queue から filings データをポップし、DuckDB へ一括保存する Consumer タスク。"""
    log = logger.bind(stage="db-filings")
    buffer = []
    while True:
        item = await queue.get()
        if item is None:  # 終了シグナル
            if buffer:
                log.info(f"Flushing final filings buffer | count={len(buffer)}")
                await asyncio.to_thread(storage.save_filings_batch, buffer)
                buffer.clear()
            queue.task_done()
            break

        buffer.append(item)
        if len(buffer) >= BATCH_SIZE:
            log.info(f"Flushing filings buffer | count={len(buffer)}")
            await asyncio.to_thread(storage.save_filings_batch, list(buffer))
            buffer.clear()
        queue.task_done()


async def _facts_db_consumer(storage: EdgarStorage, queue: asyncio.Queue):
    """バックグラウンドで Queue から facts データをポップし、DuckDB へ一括保存する Consumer タスク。"""
    log = logger.bind(stage="db-facts")
    buffer = []
    while True:
        item = await queue.get()
        if item is None:  # 終了シグナル
            if buffer:
                log.info(f"Flushing final facts buffer | count={len(buffer)}")
                await asyncio.to_thread(storage.save_facts_batch, buffer)
                buffer.clear()
            queue.task_done()
            break

        buffer.append(item)
        if len(buffer) >= BATCH_SIZE:
            log.info(f"Flushing facts buffer | count={len(buffer)}")
            await asyncio.to_thread(storage.save_facts_batch, list(buffer))
            buffer.clear()
        queue.task_done()


async def _parse_worker(
    parser: EdgarParser,
    raw_queue: asyncio.Queue,
    filings_queue: asyncio.Queue,
):
    """バックグラウンドで raw HTML をポップし、パースして filings_queue に投入する Worker タスク。"""
    log = logger.bind(stage="parse")
    while True:
        item = await raw_queue.get()
        if item is None:  # 終了シグナル
            raw_queue.task_done()
            break

        entry_or_filing, ticker, acc_no, filing_date, form_type, content = item
        try:
            sections = await asyncio.to_thread(parser.extract_all_sections, content, form_type)
            if sections:
                filing_metadata = entry_or_filing.copy()
                filing_metadata["ticker"] = ticker
                filing_metadata["accessionNumber"] = acc_no
                filing_metadata["filingDate"] = filing_date
                filing_metadata["form"] = form_type
                await filings_queue.put((filing_metadata, sections))
        except Exception:
            log.exception(f"Error parsing filing sections | acc_no={acc_no}")
        finally:
            raw_queue.task_done()


async def _download_and_queue_filing(
    entry_or_filing: dict,
    ticker: str,
    acc_no: str,
    filing_date: str,
    cik: str,
    fetcher: EdgarFetcher,
    raw_queue: asyncio.Queue,
):
    """HTML本文をダウンロードし、パースを待たずに即座に raw_queue に投入します。"""
    log = logger.bind(stage="fetch")
    doc_name = entry_or_filing.get("primaryDocument")
    if not doc_name:
        filing = await asyncio.to_thread(fetcher.resolve_filing_metadata, ticker, acc_no)
        if not filing:
            return
        doc_name = filing["primaryDocument"]
        form_type = filing.get("form", "unknown")
    else:
        form_type = entry_or_filing.get("form", "unknown")

    log.info(
        f"Downloading | ticker={ticker} | acc_no={acc_no} | filing_date={filing_date} | form={form_type}"
    )
    content = await asyncio.to_thread(fetcher.fetch_filing_content, cik, acc_no, doc_name)
    await asyncio.sleep(0.11)  # SEC レート制限（最大10 req/sec）遵守のためのウェイター

    if content:
        await raw_queue.put((entry_or_filing, ticker, acc_no, filing_date, form_type, content))


async def _extract_and_queue_facts(
    ticker: str,
    acc_no: str,
    filing_date: str,
    needs_facts_repair: bool,
    facts_queue: asyncio.Queue,
    storage: EdgarStorage | None = None,
):
    """財務数値Factsデータを抽出し、非ブロッキングで Queue に投入します。"""
    log = logger.bind(stage="facts")
    if needs_facts_repair:
        log.info(f"Repairing facts | ticker={ticker} | acc_no={acc_no} | filing_date={filing_date}")
    else:
        log.debug(f"Syncing financial facts | ticker={ticker} | acc_no={acc_no} | filing_date={filing_date}")

    facts_df = await asyncio.to_thread(EdgarQuantitative.extract_facts, acc_no)
    if not facts_df.empty:
        # DB書き込みを待たずに非ブロッキングで Queue に投入 (Producer)
        await facts_queue.put((ticker, acc_no, facts_df))
    elif storage:
        # Facts が 0 件だった場合でも、チェック済みフラグを記録して次回以降の再評価を防止
        await asyncio.to_thread(storage.mark_facts_checked, acc_no)


async def sync_recent_us_filings(
    fetcher: EdgarFetcher, parser: EdgarParser, storage: EdgarStorage, days=7
):
    """
    SEC Daily Index（日次インデックス一覧）を使用して、
    米国上場企業全体の指定過去日数分の提出書類（10-K, 10-Q）を同期・収集します。
    """
    today = date.today()
    threshold_date = (today - timedelta(days=days)).isoformat()

    raw_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    filings_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    facts_queue: asyncio.Queue = asyncio.Queue(maxsize=200)

    # バックグラウンドの Worker 及び DB 消費者タスクを起動
    parse_workers = [
        asyncio.create_task(_parse_worker(parser, raw_queue, filings_queue))
        for _ in range(4)  # 4並列パースワーカー
    ]
    filings_consumer_task = asyncio.create_task(_filings_db_consumer(storage, filings_queue))
    facts_consumer_task = asyncio.create_task(_facts_db_consumer(storage, facts_queue))

    logger.info(f"Starting sync | days={days} | threshold_date={threshold_date}")

    background_tasks: set[asyncio.Task] = set()

    try:
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

                # 全受付番号の一括判定用リスト作成とバルクDB照会
                all_acc_nos = [e["accessionNumber"] for e in filings if e.get("accessionNumber")]
                existing_filings_set = storage.filing_exists_batch(all_acc_nos)
                existing_facts_set = storage.facts_exist_batch(all_acc_nos)

                skipped_tickers = []
                pending_entries = []

                for entry in filings:
                    acc_no = entry.get("accessionNumber")
                    ticker = entry.get("ticker", "UNKNOWN")
                    filing_date = entry.get("filingDate", "unknown")

                    if ticker == "UNKNOWN" or not acc_no:
                        continue

                    needs_full_sync = acc_no not in existing_filings_set
                    needs_facts_repair = not needs_full_sync and acc_no not in existing_facts_set

                    if not needs_full_sync and not needs_facts_repair:
                        daily_skipped += 1
                        skipped_tickers.append(f"{ticker} ({filing_date})")
                    else:
                        pending_entries.append((entry, ticker, acc_no, filing_date, needs_full_sync, needs_facts_repair))

                logger.info(
                    f"Diff sync status | date={target_date} | total_found={len(filings)} | "
                    f"to_process={len(pending_entries)} | skipped={daily_skipped} (already synced)"
                )

                # 並列ダウンロード用のセマフォ（SEC制限遵守: 最大8並列）
                semaphore = asyncio.Semaphore(8)

                async def _process_entry(entry_item):
                    nonlocal daily_processed
                    entry, ticker, acc_no, filing_date, needs_full_sync, needs_facts_repair = entry_item
                    async with semaphore:
                        try:
                            if needs_full_sync:
                                cik = entry["cik"].lstrip("0")
                                await _download_and_queue_filing(
                                    entry, ticker, acc_no, filing_date, cik, fetcher, raw_queue
                                )

                            if acc_no not in existing_facts_set:
                                # Facts 抽出を非同期バックグラウンドタスクとして起動し、ダウンロードループをブロックしない
                                task = asyncio.create_task(
                                    _extract_and_queue_facts(
                                        ticker, acc_no, filing_date, needs_facts_repair, facts_queue, storage
                                    )
                                )
                                background_tasks.add(task)
                                task.add_done_callback(background_tasks.discard)
                            daily_processed += 1
                        except Exception:
                            logger.exception(f"Error processing US filing | acc_no={acc_no} | filing_date={filing_date}")


                if pending_entries:
                    await asyncio.gather(*[_process_entry(item) for item in pending_entries])

                logger.info(
                    f"Completed daily sync | date={target_date} | processed={daily_processed} | skipped={daily_skipped}"
                )
                if skipped_tickers:
                    logger.info(
                        f"Skipped filings (already synced) | date={target_date} | count={len(skipped_tickers)} | sample={', '.join(skipped_tickers[:5])}{'...' if len(skipped_tickers) > 5 else ''}"
                    )
            except Exception:
                logger.exception(f"Failed to process US index | date={target_date}")
    finally:
        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)

        # Producer 完了後、センチネル値を投入して Worker 及び Consumer をフラッシュ & クローズ
        for _ in range(len(parse_workers)):
            await raw_queue.put(None)
        await asyncio.gather(*parse_workers)

        await filings_queue.put(None)
        await facts_queue.put(None)
        await asyncio.gather(filings_consumer_task, facts_consumer_task)

    logger.info("Sync completed")


async def process_us_tickers(
    tickers, fetcher: EdgarFetcher, parser: EdgarParser, storage: EdgarStorage, days=365
):
    """
    指定された特定のティッカーシンボル群（個別指定）について、
    直近指定日数分の提出書類をピンポイントで同期・収集します。
    """
    raw_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    filings_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    facts_queue: asyncio.Queue = asyncio.Queue(maxsize=200)

    parse_workers = [
        asyncio.create_task(_parse_worker(parser, raw_queue, filings_queue))
        for _ in range(4)
    ]
    filings_consumer_task = asyncio.create_task(_filings_db_consumer(storage, filings_queue))
    facts_consumer_task = asyncio.create_task(_facts_db_consumer(storage, facts_queue))

    threshold_date = (date.today() - timedelta(days=days)).isoformat()
    logger.info(f"Processing tickers | count={len(tickers)} | threshold_date={threshold_date}")

    background_tasks: set[asyncio.Task] = set()

    try:
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

                # バルク一括照会
                target_acc_nos = [f["accessionNumber"] for f in target_filings if f.get("accessionNumber")]
                existing_filings_set = storage.filing_exists_batch(target_acc_nos)
                existing_facts_set = storage.facts_exist_batch(target_acc_nos)

                skipped_filings = []
                skipped_facts = []
                pending_target_filings = []

                for filing in target_filings:
                    acc_no = filing["accessionNumber"]
                    filing_date = filing.get("filingDate", "unknown")

                    # メモリ内 Set 判定 ($O(1)$ 高速検索)
                    needs_full_sync = acc_no not in existing_filings_set
                    needs_facts_repair = not needs_full_sync and acc_no not in existing_facts_set

                    if not needs_full_sync and not needs_facts_repair:
                        skipped_count += 1
                        skipped_filings.append(f"{filing_date} ({acc_no})")
                    else:
                        pending_target_filings.append((filing, acc_no, filing_date, needs_full_sync, needs_facts_repair))

                logger.info(
                    f"Diff sync status | ticker={ticker} | total_in_range={len(target_filings)} | "
                    f"to_process={len(pending_target_filings)} | skipped={skipped_count} (already synced)"
                )

                for filing, acc_no, filing_date, needs_full_sync, needs_facts_repair in pending_target_filings:
                    if needs_facts_repair:
                        skipped_facts.append(f"{filing_date} ({acc_no})")

                    if needs_full_sync:
                        cik = fetcher.get_cik(ticker).lstrip("0")
                        await _download_and_queue_filing(
                            filing, ticker, acc_no, filing_date, cik, fetcher, raw_queue
                        )

                    if acc_no not in existing_facts_set:
                        task = asyncio.create_task(
                            _extract_and_queue_facts(
                                ticker, acc_no, filing_date, needs_facts_repair, facts_queue, storage
                            )
                        )
                        background_tasks.add(task)
                        task.add_done_callback(background_tasks.discard)
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
    finally:
        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)
        for _ in range(len(parse_workers)):
            await raw_queue.put(None)
        await asyncio.gather(*parse_workers)

        await filings_queue.put(None)
        await facts_queue.put(None)
        await asyncio.gather(filings_consumer_task, facts_consumer_task)

    logger.info("Ticker processing completed")


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
                storage.mark_facts_checked(acc_no)

            await asyncio.sleep(0.1)
        except Exception:
            logger.exception(f"Failed to repair facts for {acc_no}")


    # 残りのバッファを一括書き込み
    if facts_buffer:
        logger.info(f"Flushing final facts buffer | count={len(facts_buffer)}")
        storage.save_facts_batch(facts_buffer)
