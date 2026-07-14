import asyncio
import gc
from datetime import date, timedelta

import requests
from loguru import logger

from .fetcher import EdgarFetcher
from .parser import EdgarParser
from .quantitative import EdgarQuantitative
from .storage import DataIntegrityError, EdgarStorage


async def sync_recent_us_filings(
    fetcher: EdgarFetcher, parser: EdgarParser, storage: EdgarStorage, days=7
):
    """
    SEC Daily Index（日次インデックス一覧）を使用して、
    米国上場企業全体の指定過去日数分の提出書類（10-K, 10-Q）を同期・収集します。
    """
    today = date.today()

    for i in range(days):
        # 今日から指定日数分、過去に遡って1日ずつインデックスを処理
        target_date = today - timedelta(days=i)
        logger.info(f"Syncing US filings via daily index | date={target_date}")

        try:
            # 1. SEC Daily Index から対象日の提出書類一覧を取得
            filings = await asyncio.to_thread(fetcher.list_daily_filings, target_date)
            if not filings:
                # 週末・祝日などで提出書類リストがない場合はスキップ
                continue

            for entry in filings:
                try:
                    acc_no = entry["accessionNumber"]
                    ticker = entry.get("ticker")

                    # ティッカーが解決できない特殊な書類は同期対象から除外
                    if not ticker or ticker == "UNKNOWN":
                        continue

                    # スマートリペア（Smart Repair）ロジックによる差分同期判定
                    # 書類メタデータ/テキストが未保存かを確認
                    needs_full_sync = not storage.filing_exists(acc_no)
                    # 書類はあるが財務数値Factsデータのみが欠けているか確認
                    needs_facts_repair = not needs_full_sync and not storage.facts_exist(acc_no)

                    # 両方揃っている場合は処理をスキップ（高速化）
                    if not needs_full_sync and not needs_facts_repair:
                        continue

                    # メタデータおよび定性テキスト（本文）が未取得の場合、ダウンロードと保存を実行
                    if needs_full_sync:
                        # インデックスに含まれない詳細なメタデータ（主ファイル名等）を解決
                        logger.info(f"Resolving metadata | ticker={ticker} | acc_no={acc_no}")
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
                        logger.info(f"Downloading | ticker={ticker} | acc_no={acc_no}")
                        resp = await asyncio.to_thread(
                            requests.get, url, headers=fetcher.headers, timeout=30
                        )
                        # SECのアクセス制限（1秒間10リクエスト）を回避するために適切な待機時間を挿入
                        await asyncio.sleep(0.11)

                        if resp.status_code == 200:
                            # HTMLテキストから各セクション（MD&A、Businessなど）をパース・抽出
                            sections = parser.extract_all_sections(resp.text, filing["form"])
                            if sections:
                                try:
                                    filing_metadata = filing.copy()
                                    filing_metadata["ticker"] = ticker
                                    filing_metadata["cik"] = cik
                                    # 定性テキスト情報をDBへ保存
                                    storage.save_filing(filing_metadata, sections)
                                except DataIntegrityError as e:
                                    logger.error(
                                        f"Filing integrity check failed | acc_no={acc_no} | error={e}"
                                    )
                        del resp

                    # 定量（財務数値Facts）データの抽出および保存
                    logger.info(f"Syncing financial facts | ticker={ticker} | acc_no={acc_no}")
                    facts_df = await asyncio.to_thread(EdgarQuantitative.extract_facts, acc_no)
                    if not facts_df.empty:
                        try:
                            # 財務数値をDBへ保存
                            storage.save_facts(ticker, acc_no, facts_df)
                        except DataIntegrityError as e:
                            logger.error(
                                f"Facts integrity check failed | acc_no={acc_no} | error={e}"
                            )

                    # メモリ節約のため定期的にガーベジコレクションを明示的に呼び出し
                    gc.collect()
                except Exception:
                    logger.exception(f"Error processing US filing | acc_no={acc_no}")
        except Exception:
            logger.exception(f"Failed to process US index | date={target_date}")


async def process_us_tickers(
    tickers, fetcher: EdgarFetcher, parser: EdgarParser, storage: EdgarStorage, days=365
):
    """
    指定された特定のティッカーシンボル群（個別指定）について、
    直近指定日数分の提出書類をピンポイントで同期・収集します。
    """
    for ticker in tickers:
        try:
            logger.info(f"Processing ticker | ticker={ticker}")
            # 対象企業の全提出履歴メタデータを取得
            subs = await asyncio.to_thread(fetcher.get_latest_submissions, ticker)
            if not subs:
                continue

            # 10-K, 10-Q書類のみをフィルタリング
            filings = fetcher.filter_relevant_filings(subs)
            if not filings:
                continue

            # 指定日数前の基準日付を設定
            threshold_date = (date.today() - timedelta(days=days)).isoformat()
            target_filings = [f for f in filings if f["filingDate"] >= threshold_date]

            for filing in target_filings:
                acc_no = filing["accessionNumber"]

                # 差分確認（定性・定量の存在チェック）
                needs_full_sync = not storage.filing_exists(acc_no)
                needs_facts_repair = not needs_full_sync and not storage.facts_exist(acc_no)

                if not needs_full_sync and not needs_facts_repair:
                    continue

                if needs_full_sync:
                    # ダウンロードと定性テキスト保存
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
                            try:
                                filing_metadata = filing.copy()
                                filing_metadata["ticker"] = ticker
                                filing_metadata["cik"] = cik
                                storage.save_filing(filing_metadata, sections)
                            except DataIntegrityError as e:
                                logger.error(
                                    f"Filing integrity check failed | ticker={ticker} | error={e}"
                                )
                    del resp

                # 定量データの抽出と保存
                logger.info(f"Syncing financial facts | ticker={ticker} | acc_no={acc_no}")
                facts_df = await asyncio.to_thread(EdgarQuantitative.extract_facts, acc_no)
                if not facts_df.empty:
                    try:
                        storage.save_facts(ticker, acc_no, facts_df)
                    except DataIntegrityError as e:
                        logger.error(f"Facts integrity check failed | ticker={ticker} | error={e}")

                gc.collect()
        except Exception:
            logger.exception(f"Failed to process ticker | ticker={ticker}")


async def repair_all_missing_facts(storage: EdgarStorage):
    """
    データ整合性の「自己修復（リペア）」バッチ。
    データベース内の全レコードを走査し、定性データ（報告書本文）はあるが
    定量数値データ（Facts）が欠落しているレコードを検出して、自動的にXBRLデータを再抽出し修復します。
    """
    targets = storage.get_accession_numbers_needing_repair()
    logger.info(f"Found {len(targets)} filings needing facts repair.")

    for acc_no, ticker in targets:
        try:
            logger.info(f"Repairing facts | ticker={ticker} | acc_no={acc_no}")
            facts_df = await asyncio.to_thread(EdgarQuantitative.extract_facts, acc_no)
            if not facts_df.empty:
                try:
                    storage.save_facts(ticker, acc_no, facts_df)
                except DataIntegrityError as e:
                    logger.error(
                        f"Facts integrity check failed during repair | acc_no={acc_no} | error={e}"
                    )
            else:
                logger.warning(f"No facts found during repair for {acc_no}")

            await asyncio.sleep(0.1)
            gc.collect()
        except Exception:
            logger.exception(f"Failed to repair facts for {acc_no}")
