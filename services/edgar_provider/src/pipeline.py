import asyncio
import os
from datetime import date, timedelta

import requests
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


async def sync_recent_us_filings(
    fetcher: EdgarFetcher, parser: EdgarParser, storage: EdgarStorage, days=7
):
    """
    SEC Daily Index（日次インデックス一覧）を使用して、
    米国上場企業全体の指定過去日数分の提出書類（10-K, 10-Q）を同期・収集します。
    """
    today = date.today()
    threshold_date = (today - timedelta(days=days)).isoformat()

    # バッチ処理用のバッファ
    filings_buffer: list[tuple[dict, dict]] = []
    facts_buffer: list[tuple[str, str, any]] = []

    logger.info(f"Starting sync | days={days} | threshold_date={threshold_date}")

    for i in range(days):
        # 今日から指定日数分、過去に遡って1日ずつインデックスを処理
        target_date = today - timedelta(days=i)
        daily_skipped = 0
        daily_processed = 0
        logger.info(f"Syncing US filings via daily index | date={target_date}")

        try:
            # 1. SEC Daily Index から対象日の提出書類一覧を取得
            filings = await asyncio.to_thread(fetcher.list_daily_filings, target_date)
            if not filings:
                # 週末・祝日などで提出書類リストがない場合はスキップ
                logger.debug(f"No filings found for date (weekend/holiday) | date={target_date}")
                continue

            logger.info(f"Found filings in daily index | date={target_date} | count={len(filings)}")

            for entry in filings:
                try:
                    acc_no = entry["accessionNumber"]
                    ticker = entry.get("ticker")
                    filing_date = entry.get("filingDate", "unknown")

                    # ティッカーが解決できない特殊な書類は同期対象から除外
                    if not ticker or ticker == "UNKNOWN":
                        logger.debug(f"Skipping unknown ticker | acc_no={acc_no}")
                        continue

                    # スマートリペア（Smart Repair）ロジックによる差分同期判定
                    # 書類メタデータ/テキストが未保存かを確認
                    needs_full_sync = not storage.filing_exists(acc_no)
                    # 書類はあるが財務数値Factsデータのみが欠けているか確認
                    needs_facts_repair = not needs_full_sync and not storage.facts_exist(acc_no)

                    # 両方揃っている場合は処理をスキップ（高速化）
                    if not needs_full_sync and not needs_facts_repair:
                        daily_skipped += 1
                        logger.debug(
                            f"Skipping (already synced) | ticker={ticker} | acc_no={acc_no} | filing_date={filing_date}"
                        )
                        continue

                    # メタデータおよび定性テキスト（本文）が未取得の場合、ダウンロードと保存を実行
                    if needs_full_sync:
                        # インデックスに含まれない詳細なメタデータ（主ファイル名等）を解決
                        logger.debug(
                            f"Resolving metadata | ticker={ticker} | acc_no={acc_no} | filing_date={filing_date}"
                        )
                        filing = await asyncio.to_thread(
                            fetcher.resolve_filing_metadata, ticker, acc_no
                        )
                        if not filing:
                            continue

                        # ダウンロード用URLの構築
                        cik = entry["cik"].lstrip("0")
                        acc_no_clean = acc_no.replace("-", "")
                        doc_name = filing["primaryDocument"]
                        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_clean}/{doc_name}"

                        # HTML書類をダウンロード
                        logger.info(
                            f"Downloading | ticker={ticker} | acc_no={acc_no} | filing_date={filing_date} | form={entry.get('form', 'unknown')}"
                        )
                        resp = await asyncio.to_thread(
                            requests.get, url, headers=fetcher.headers, timeout=30
                        )
                        # SECのアクセス制限（1秒間10リクエスト）を回避するために適切な待機時間を挿入
                        await asyncio.sleep(0.11)

                        if resp.status_code == 200:
                            # HTMLテキストから各セクション（MD&A、Businessなど）をパース・抽出
                            sections = parser.extract_all_sections(resp.text, filing["form"])
                            if sections:
                                filing_metadata = filing.copy()
                                filing_metadata["ticker"] = ticker
                                filing_metadata["cik"] = cik
                                # バッファに追加
                                filings_buffer.append((filing_metadata, sections))

                                # バッチサイズに達したら一括書き込み
                                if len(filings_buffer) >= BATCH_SIZE:
                                    logger.info(
                                        f"Flushing filings buffer | count={len(filings_buffer)} | filing_date={filing_date}"
                                    )
                                    storage.save_filings_batch(filings_buffer)
                                    filings_buffer.clear()
                        del resp

                    # 定量（財務数値Facts）データの抽出および保存
                    if needs_facts_repair:
                        logger.info(
                            f"Repairing facts | ticker={ticker} | acc_no={acc_no} | filing_date={filing_date}"
                        )
                    else:
                        logger.debug(
                            f"Syncing financial facts | ticker={ticker} | acc_no={acc_no} | filing_date={filing_date}"
                        )
                    facts_df = await asyncio.to_thread(EdgarQuantitative.extract_facts, acc_no)
                    if not facts_df.empty:
                        facts_buffer.append((ticker, acc_no, facts_df))

                        # バッチサイズに達したら一括書き込み
                        if len(facts_buffer) >= BATCH_SIZE:
                            logger.info(
                                f"Flushing facts buffer | count={len(facts_buffer)} | filing_date={filing_date}"
                            )
                            storage.save_facts_batch(facts_buffer)
                            facts_buffer.clear()

                    daily_processed += 1

                except Exception:
                    logger.exception(f"Error processing US filing | acc_no={acc_no} | filing_date={filing_date}")

            # 日付ごとの処理完了サマリー
            logger.info(
                f"Completed daily sync | date={target_date} | processed={daily_processed} | skipped={daily_skipped}"
            )
        except Exception:
            logger.exception(f"Failed to process US index | date={target_date}")

    # 残りのバッファを一括書き込み
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
    # バッチ処理用のバッファ
    filings_buffer: list[tuple[dict, dict]] = []
    facts_buffer: list[tuple[str, str, any]] = []

    # 基準日付を計算
    threshold_date = (date.today() - timedelta(days=days)).isoformat()
    logger.info(f"Processing tickers | count={len(tickers)} | threshold_date={threshold_date}")

    for ticker in tickers:
        skipped_count = 0
        processed_count = 0
        try:
            logger.info(f"Processing ticker | ticker={ticker}")
            # 対象企業の全提出履歴メタデータを取得
            subs = await asyncio.to_thread(fetcher.get_latest_submissions, ticker)
            if not subs:
                logger.warning(f"No submissions found | ticker={ticker}")
                continue

            # 10-K, 10-Q書類のみをフィルタリング
            filings = fetcher.filter_relevant_filings(subs)
            if not filings:
                logger.warning(f"No 10-K/10-Q filings found | ticker={ticker}")
                continue

            # 指定日数前の基準日付を設定
            target_filings = [f for f in filings if f["filingDate"] >= threshold_date]
            logger.info(
                f"Found filings | ticker={ticker} | total={len(filings)} | "
                f"in_range={len(target_filings)} | threshold={threshold_date}"
            )

            for filing in target_filings:
                acc_no = filing["accessionNumber"]
                filing_date = filing.get("filingDate", "unknown")

                # 差分確認（定性・定量の存在チェック）
                needs_full_sync = not storage.filing_exists(acc_no)
                needs_facts_repair = not needs_full_sync and not storage.facts_exist(acc_no)

                if not needs_full_sync and not needs_facts_repair:
                    skipped_count += 1
                    logger.debug(
                        f"Skipping (already synced) | ticker={ticker} | acc_no={acc_no} | filing_date={filing_date}"
                    )
                    continue

                if needs_full_sync:
                    # ダウンロードと定性テキスト保存
                    cik = fetcher.get_cik(ticker).lstrip("0")
                    acc_no_clean = acc_no.replace("-", "")
                    doc_name = filing["primaryDocument"]
                    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_clean}/{doc_name}"

                    logger.info(
                        f"Downloading | ticker={ticker} | acc_no={acc_no} | filing_date={filing_date} | form={filing.get('form', 'unknown')}"
                    )
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
                            filings_buffer.append((filing_metadata, sections))

                            # バッチサイズに達したら一括書き込み
                            if len(filings_buffer) >= BATCH_SIZE:
                                logger.info(
                                    f"Flushing filings buffer | count={len(filings_buffer)} | ticker={ticker}"
                                )
                                storage.save_filings_batch(filings_buffer)
                                filings_buffer.clear()
                    del resp

                # 定量データの抽出と保存
                if needs_facts_repair:
                    logger.info(
                        f"Repairing facts | ticker={ticker} | acc_no={acc_no} | filing_date={filing_date}"
                    )
                else:
                    logger.debug(
                        f"Syncing financial facts | ticker={ticker} | acc_no={acc_no} | filing_date={filing_date}"
                    )
                facts_df = await asyncio.to_thread(EdgarQuantitative.extract_facts, acc_no)
                if not facts_df.empty:
                    facts_buffer.append((ticker, acc_no, facts_df))

                    # バッチサイズに達したら一括書き込み
                    if len(facts_buffer) >= BATCH_SIZE:
                        logger.info(
                            f"Flushing facts buffer | count={len(facts_buffer)} | ticker={ticker}"
                        )
                        storage.save_facts_batch(facts_buffer)
                        facts_buffer.clear()

                processed_count += 1

            # ティッカーごとの処理完了サマリー
            logger.info(
                f"Completed ticker | ticker={ticker} | processed={processed_count} | skipped={skipped_count}"
            )
        except Exception:
            logger.exception(f"Failed to process ticker | ticker={ticker}")

    # 残りのバッファを一括書き込み
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
