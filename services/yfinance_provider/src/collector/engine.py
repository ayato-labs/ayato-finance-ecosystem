import json
import os
import random
import time
import threading
import queue
import concurrent.futures
from datetime import datetime, timedelta
import hashlib

import pandas as pd
import yfinance as yf
from yfinance.exceptions import YFRateLimitError

from ..core.db_manager import DatabaseManager
from ..core.logging import setup_logger
from ..core.validator import DataValidator

logger = setup_logger(app_name="collector_engine")


class SyncEngine:
    def __init__(self, db_manager: DatabaseManager, max_workers: int = 4):
        self.db = db_manager
        self.max_workers = max_workers
        self.validator = DataValidator()
        self.write_queue = queue.Queue()
        self.stop_event = threading.Event()
        self._rate_limit_lock = threading.Lock()
        self._backoff_until = 0.0  # Unix timestamp

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

    def _calculate_profile_hash(self, info_raw: dict) -> str:
        """定性情報のハッシュ値を計算する"""
        qualitative_fields = [
            "longName",
            "sector",
            "industry",
            "longBusinessSummary",
            "website",
            "fullTimeEmployees",
        ]
        text_data = ""
        for field in qualitative_fields:
            val = info_raw.get(field)
            if val is not None:
                text_data += f"{field}:{val}|"
        return hashlib.md5(text_data.encode("utf-8")).hexdigest()

    def _update_profile_history(self, profile_path: str, info_raw: dict, current_hash: str) -> bool:
        """プロフィールの履歴を更新する（SCD Type 2）"""
        history = []
        if os.path.exists(profile_path):
            try:
                with open(profile_path, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                logger.warning(f"Failed to read history from {profile_path}. Re-creating.")
                history = []

        if history and isinstance(history, list):
            last_entry = history[-1]
            if last_entry.get("hash") == current_hash:
                return False  # 変更なし

        # 必要なフィールドの抽出
        entry = {
            "valid_from": datetime.now().strftime("%Y-%m-%d"),
            "hash": current_hash,
            "longName": info_raw.get("longName"),
            "sector": info_raw.get("sector"),
            "industry": info_raw.get("industry"),
            "longBusinessSummary": info_raw.get("longBusinessSummary"),
            "website": info_raw.get("website"),
            "fullTimeEmployees": info_raw.get("fullTimeEmployees"),
        }

        history.append(entry)

        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

        return True

    def _fetch_task(self, ticker: str, force: bool = False):
        """個別銘柄の取得とバリデーション (並列実行用)"""
        while True:
            wait_time = self._backoff_until - time.perf_counter()
            if wait_time <= 0:
                break
            logger.warning(f"[{ticker}] Global backoff in effect. Waiting {wait_time:.1f}s...")
            time.sleep(min(wait_time, 5.0))

        time.sleep(random.uniform(0.5, 2.0))

        start_time = time.perf_counter()
        logger.info(f"[{ticker}] Starting sync task...")

        try:
            profile_dir = os.path.join("data", "profiles")
            profile_path = os.path.join(profile_dir, f"{ticker}.json")
            info_raw = None
            need_fetch_info = True

            if os.path.exists(profile_path):
                mtime = os.path.getmtime(profile_path)
                if not force and time.time() - mtime < 7 * 24 * 3600:
                    need_fetch_info = False
                    logger.debug(f"[{ticker}] Profile is recent (7d). Skipping yt.info")
                    try:
                        with open(profile_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            if isinstance(data, list) and len(data) > 0:
                                info_raw = data[-1]
                            else:
                                info_raw = data
                    except Exception:
                        logger.warning(f"[{ticker}] Failed to read cached profile")
                        need_fetch_info = True

            yt = yf.Ticker(ticker)

            if need_fetch_info:
                info_raw = yt.info

            if not info_raw or "longName" not in info_raw:
                elapsed = time.perf_counter() - start_time
                logger.warning(
                    f"[{ticker}] Crucial data missing (possibly invalid). Skipping. ({elapsed:.2f}s)"
                )
                self.write_queue.put(
                    (self._update_status_only, (ticker, "FAILED", "Crucial data missing"))
                )
                return

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

            prices_df = yt.history(period="max")
            if not prices_df.empty:
                prices_df = prices_df.reset_index()
                prices_df["ticker"] = ticker
                prices_df.columns = [str(c).lower().replace(" ", "_") for c in prices_df.columns]
                
                # Apply logical validation (OHLC relations, NaN handling)
                prices_df = self.validator.check_logical(prices_df)

            if prices_df.empty:
                logger.warning(f"[{ticker}] No valid price data after validation. Skipping.")
                self.write_queue.put(
                    (self._update_status_only, (ticker, "FAILED", "No valid price data"))
                )
                return

            self.write_queue.put((self._write_to_db, (ticker, info_raw, financials, prices_df)))
            elapsed = time.perf_counter() - start_time
            logger.info(f"[{ticker}] Task queued in {elapsed:.2f}s")

        except YFRateLimitError:
            with self._rate_limit_lock:
                if time.perf_counter() > self._backoff_until:
                    logger.error(f"[{ticker}] HIT RATE LIMIT (429). Pausing engine for 60s...")
                    self._backoff_until = time.perf_counter() + 60.0
            self.write_queue.put((self._update_status_only, (ticker, "FAILED", "Rate limited")))

        except Exception as e:
            elapsed = time.perf_counter() - start_time
            logger.exception(f"[{ticker}] Unexpected Fetch/Validation error after {elapsed:.2f}s")
            self.write_queue.put((self._update_status_only, (ticker, "FAILED", str(e))))

    def _write_to_db(self, conn, ticker, info_raw, financials, prices_df):
        """DBへの書き込み処理 (DBワーカーから呼ばれる)"""
        start_time = time.perf_counter()
        try:
            # 1. 定性情報の保存（JSON履歴）
            profile_dir = os.path.join("data", "profiles")
            os.makedirs(profile_dir, exist_ok=True)
            profile_path = os.path.join(profile_dir, f"{ticker}.json")

            current_hash = self._calculate_profile_hash(info_raw)
            if self._update_profile_history(profile_path, info_raw, current_hash):
                logger.info(f"[{ticker}] Updated profile history with hash {current_hash[:8]}")

            # 2. 数値データをDBに保存
            conn.execute(
                "INSERT OR REPLACE INTO info (ticker, data) VALUES (?, ?)",
                [ticker, json.dumps(info_raw, ensure_ascii=False)],
            )

            for df, table in financials:
                if df is not None:
                    query = f"""
                        INSERT OR REPLACE INTO {table} (ticker, date, item, value, period_type)
                        SELECT ticker, date, item, value, period_type FROM df
                    """
                    conn.execute(query)

            if prices_df is not None and not prices_df.empty:
                query = """
                    INSERT OR REPLACE INTO prices (ticker, date, open, high, low, close, volume,
                                        dividends, stock_splits)
                    SELECT ticker, date, open, high, low, close, volume,
                           dividends, stock_splits FROM prices_df
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
        synced_df = conn.execute("SELECT ticker, last_sync_at, last_status FROM sync_status").df()
        conn.close()

        to_fetch = []
        for t in tickers:
            if force:
                to_fetch.append(t)
                continue

            if not synced_df.empty and t in synced_df["ticker"].values:
                row = synced_df[synced_df["ticker"] == t].iloc[0]
                last_sync = row["last_sync_at"]
                last_status = row["last_status"]

                if last_status == "SUCCESS" and datetime.now() - last_sync < timedelta(hours=24):
                    logger.debug(f"[{t}] Skipping: Synced successfully within 24h ({last_sync})")
                    continue

                if last_status == "FAILED" and datetime.now() - last_sync < timedelta(minutes=5):
                    logger.debug(f"[{t}] Skipping: Failed recently, cooling down... ({last_sync})")
                    continue

            to_fetch.append(t)

        if not to_fetch:
            logger.info("No tickers need syncing.")
            return

        writer_thread = threading.Thread(target=self._db_worker)
        writer_thread.start()

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # force を渡すために lambda を使用
            futures = [executor.submit(self._fetch_task, t, force) for t in to_fetch]
            concurrent.futures.wait(futures)

        self.stop_event.set()
        writer_thread.join()
        logger.success("Sync session finished.")
