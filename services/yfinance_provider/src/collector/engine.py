import concurrent.futures
import json
import queue
import threading
import time
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from ..core.db_manager import DatabaseManager
from ..core.logger import setup_logger
from ..core.schema import TickerInfo

logger = setup_logger("collector_engine")


class SyncEngine:
    def __init__(self, db_manager: DatabaseManager, max_workers: int = 4):
        self.db = db_manager
        self.max_workers = max_workers
        self.write_queue = queue.Queue()
        self.stop_event = threading.Event()

    def _db_worker(self):
        """直列書き込み用ワーカー"""
        logger.info("Database write worker started.")
        conn = self.db.get_connection()
        while not self.stop_event.is_set() or not self.write_queue.empty():
            try:
                task = self.write_queue.get(timeout=1.0)
                if task is None:
                    break
                func, args = task
                func(conn, *args)
                self.write_queue.task_done()
            except queue.Empty:
                continue
            except Exception:
                logger.exception("Error in Database Write Worker")
        conn.close()
        logger.info("Database write worker stopped.")

    def _fetch_task(self, ticker: str):
        """個別銘柄の取得とバリデーション (並列実行用)"""
        start_time = time.perf_counter()
        logger.info(f"[{ticker}] Starting sync task...")
        try:
            yt = yf.Ticker(ticker)
            info_raw = yt.info

            # データ欠落チェック
            if not info_raw or "longName" not in info_raw:
                elapsed = time.perf_counter() - start_time
                logger.warning(
                    f"[{ticker}] Crucial data missing (possibly invalid). Skipping. ({elapsed:.2f}s)"
                )
                self.write_queue.put(
                    (self._update_status_only, (ticker, "FAILED", "Crucial data missing"))
                )
                return

            info_model = TickerInfo(raw_json=json.dumps(info_raw), **info_raw)

            def get_long_df(df, p_type):
                if df is None or df.empty:
                    return None
                if isinstance(df, pd.Series):
                    df = df.to_frame()
                ds = df.stack().reset_index()
                ds.columns = ["item", "date", "value"]
                ds["ticker"] = ticker
                ds["period_type"] = p_type
                ds["date"] = pd.to_datetime(ds["date"]).dt.strftime("%Y-%m-%d")
                return ds.dropna(subset=["value"])

            financials = [
                (get_long_df(yt.financials, "Annual"), "financials"),
                (get_long_df(yt.quarterly_financials, "Quarterly"), "financials"),
                (get_long_df(yt.balance_sheet, "Annual"), "balance_sheet"),
                (get_long_df(yt.quarterly_balance_sheet, "Quarterly"), "balance_sheet"),
                (get_long_df(yt.cashflow, "Annual"), "cashflow"),
                (get_long_df(yt.quarterly_cashflow, "Quarterly"), "cashflow"),
            ]

            prices_df = yt.history(period="5y")
            if not prices_df.empty:
                prices_df = prices_df.reset_index()
                prices_df["ticker"] = ticker
                prices_df.columns = [str(c).lower().replace(" ", "_") for c in prices_df.columns]

            self.write_queue.put((self._write_to_db, (ticker, info_model, financials, prices_df)))
            elapsed = time.perf_counter() - start_time
            logger.info(f"[{ticker}] Task queued in {elapsed:.2f}s")

        except Exception as e:
            elapsed = time.perf_counter() - start_time
            logger.exception(f"[{ticker}] Unexpected Fetch/Validation error after {elapsed:.2f}s")
            # 予期せぬエラーもキュー経由でDB更新
            self.write_queue.put((self._update_status_only, (ticker, "FAILED", str(e))))

    def _write_to_db(self, conn, ticker, info, financials, prices):
        """DBへの書き込み処理 (DBワーカーから呼ばれる)"""
        start_time = time.perf_counter()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO info (ticker, data) VALUES (?, ?)", [ticker, info.raw_json]
            )
            for df, table in financials:
                if df is not None:
                    query = f"""
                        INSERT INTO {table} (ticker, date, item, value, period_type)
                        SELECT ticker, date, item, value, period_type FROM df
                    """
                    conn.execute(query)

            if prices is not None and not prices.empty:
                query = """
                    INSERT INTO prices (ticker, date, open, high, low, close, volume,
                                        dividends, stock_splits)
                    SELECT ticker, date, open, high, low, close, volume,
                           dividends, stock_splits FROM prices
                """
                conn.execute(query)

            elapsed = time.perf_counter() - start_time
            logger.success(f"[{ticker}] DB write completed in {elapsed:.2f}s")
            self.db.update_sync_status(ticker, "SUCCESS", conn=conn)

        except Exception as e:
            elapsed = time.perf_counter() - start_time
            logger.exception(f"[{ticker}] Critical Error during DB Write after {elapsed:.2f}s")
            self.db.update_sync_status(ticker, "FAILED", error=str(e), conn=conn)

    def _update_status_only(self, conn, ticker, status, error=None):
        """ステータスのみの更新 (DBワーカーから呼ばれる)"""
        self.db.update_sync_status(ticker, status, error=error, conn=conn)

    def run_sync(self, tickers: list[str], force: bool = False):
        """全銘柄の同期実行 (差分更新対応)"""
        logger.info(f"Starting sync session for {len(tickers)} tickers (force={force})...")
        conn = self.db.get_connection()
        synced_df = conn.execute("SELECT ticker, last_sync_at FROM sync_status").df()
        conn.close()

        to_fetch = []
        for t in tickers:
            if force:
                to_fetch.append(t)
                continue
            if not synced_df.empty and t in synced_df["ticker"].values:
                last_sync = synced_df[synced_df["ticker"] == t]["last_sync_at"].iloc[0]
                if datetime.now() - last_sync < timedelta(hours=24):
                    logger.debug(f"[{t}] Skipping: Synced recently ({last_sync})")
                    continue
            to_fetch.append(t)

        if not to_fetch:
            logger.info("No tickers need syncing.")
            return

        writer_thread = threading.Thread(target=self._db_worker)
        writer_thread.start()

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            executor.map(self._fetch_task, to_fetch)

        self.stop_event.set()
        writer_thread.join()
        logger.success("Sync session finished.")
