import datetime
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import duckdb
from loguru import logger

from src.core.audit_manager import audit_manager
from src.engines.jp_engine import JPEngine
from src.engines.us_engine import USEngine
from src.mappers.ai_mapper import AIMapper


class BatchSyncService:
    def __init__(self, start_workers: bool = True):
        self.us_engine = USEngine()
        self.jp_engine = JPEngine()
        self.mapper = AIMapper()
        audit_manager._init_db()

        # 3-Thread Architecture Queues (Producer-Consumer)
        self.db_queue = queue.Queue()
        self.ai_queue = queue.Queue()
        self.is_running = True

        # Stats tracking for the current session
        self._stats_lock = threading.Lock()
        self.session_stats = {"SUCCESS": 0, "ERROR": 0}

        # Start background workers if requested
        self.db_thread = None
        self.ai_thread = None
        if start_workers:
            self.db_thread = threading.Thread(
                target=self._db_writer_worker, daemon=True, name="DBWriter"
            )
            self.ai_thread = threading.Thread(
                target=self._ai_mapper_worker, daemon=True, name="AIMapper"
            )
            self.db_thread.start()
            self.ai_thread.start()

    def stop(self):
        """Safely signal background threads to terminate."""
        logger.info("Stopping BatchSyncService...")
        self.is_running = False

        # 1. Shutdown AI Mapper executor (stop new tasks)
        self.mapper.shutdown(wait=False)

        # 2. Push sentinels to wake up queue.get() if threads are waiting
        self.db_queue.put(None)
        self.ai_queue.put(None)

        # 3. Wait for worker threads to exit
        if self.db_thread and self.db_thread.is_alive():
            self.db_thread.join(timeout=2.0)
        if self.ai_thread and self.ai_thread.is_alive():
            self.ai_thread.join(timeout=2.0)

        logger.info("BatchSyncService stopped.")

    def _db_writer_worker(self):
        """【Thread 1: DB Writer】 データベース書き込みを直列化し、競合を完全に防ぐスレッド"""
        logger.info("DB Writer Thread started.")
        while self.is_running:
            task = None
            try:
                task = self.db_queue.get(timeout=1.0)
                if task is None:
                    self.db_queue.task_done()
                    break

                task_type = task[0]

                try:
                    if task_type == "US_INGEST":
                        _, ticker, data, session_id = task
                        logger.info(f"[DBWriter] Ingesting US facts for {ticker}...")
                        self.us_engine.ingest_facts(ticker, data, session_id)
                        audit_manager.log_ticker_sync("US", ticker, 1, "SUCCESS")
                        self._increment_stat("SUCCESS")
                        self._queue_unmapped_tags("US", ticker, session_id)

                    elif task_type == "JP_INGEST":
                        _, code, df, session_id = task
                        logger.info(f"[DBWriter] Ingesting JP facts for {code}...")
                        self.jp_engine.ingest_facts(code, df, session_id)
                        audit_manager.log_ticker_sync("JP", code, 1, "SUCCESS")
                        self._increment_stat("SUCCESS")
                        self._queue_unmapped_tags("JP", code, session_id)

                    elif task_type == "JP_INGEST_BULK":
                        _, date_str, df, session_id = task
                        # In bulk mode, we group by ticker code and ingest each group
                        # Note: J-Quants bulk might use 'LocalCode' or 'Code'
                        if "LocalCode" in df.columns:
                            code_col = "LocalCode"
                        elif "Code" in df.columns:
                            code_col = "Code"
                        else:
                            code_col = "code"

                        unique_codes = df[code_col].unique()
                        logger.info(
                            f"[DBWriter] Ingesting bulk JP data for {len(unique_codes)} tickers from {date_str}..."
                        )

                        for code in unique_codes:
                            ticker_df = df[df[code_col] == code]
                            # Normalize column name for engine
                            ticker_code = str(code)
                            self.jp_engine.ingest_facts(ticker_code, ticker_df, session_id)
                            audit_manager.log_ticker_sync("JP", ticker_code, 1, "SUCCESS")
                            self._increment_stat("SUCCESS")
                            # We don't queue mapping for EVERY ticker in bulk to avoid overloading AI queue
                            # It will be caught in subsequent runs or we can sample it

                    elif task_type == "LOG_ERROR":
                        _, market, symbol, err_msg = task
                        audit_manager.log_ticker_sync(market, symbol, 0, f"ERROR: {err_msg}")
                        self._increment_stat("ERROR")

                    elif task_type == "SAVE_MAPPING":
                        _, session_id, source_tag, mapped_label, model, reasoning, conf = task
                        audit_manager.log_mapping(
                            session_id, source_tag, mapped_label, reasoning, conf, model
                        )

                    elif task_type == "LOG_SKIP":
                        _, market, symbol, reason = task
                        logger.info(f"Recording skip for {market}:{symbol} (Reason: {reason})")
                        audit_manager.log_ticker_sync(market, symbol, 0, "SKIPPED_NOT_FOUND")

                except Exception as e:
                    err_msg = str(e)
                    # If it's a lock/IO error, it's transient. Re-queue the task at the end.
                    if any(
                        kw in err_msg.lower()
                        for kw in ["io error", "locked", "permission", "used by"]
                    ):
                        logger.warning(
                            f"Transient DB Error ({task_type}). Re-queueing task. Error: {err_msg[:100]}"
                        )
                        time.sleep(0.5)  # Throttling
                        self.db_queue.put(task)
                    else:
                        logger.error(
                            f"Fatal DB Writer Error processing {task_type}: {e}", exc_info=True
                        )
                finally:
                    self.db_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Critical error in DB Writer main loop: {e}", exc_info=True)
                if task:
                    self.db_queue.task_done()

    def _process_db_task(self, task):
        """Processes a single database task based on its type."""
        task_type = task[0]
        if task_type == "US_INGEST":
            _, ticker, data, session_id = task
            logger.info(f"[DBWriter] Ingesting US facts for {ticker}...")
            self.us_engine.ingest_facts(ticker, data, session_id)
            audit_manager.log_ticker_sync("US", ticker, 1, "SUCCESS")
            self._increment_stat("SUCCESS")
            self._queue_unmapped_tags("US", ticker, session_id)

        elif task_type == "JP_INGEST":
            _, code, df, session_id = task
            logger.info(f"[DBWriter] Ingesting JP facts for {code}...")
            self.jp_engine.ingest_facts(code, df, session_id)
            audit_manager.log_ticker_sync("JP", code, 1, "SUCCESS")
            self._increment_stat("SUCCESS")
            self._queue_unmapped_tags("JP", code, session_id)

        elif task_type == "JP_INGEST_BULK":
            self._process_jp_bulk_ingest(task)

        elif task_type == "LOG_ERROR":
            _, market, symbol, err_msg = task
            audit_manager.log_ticker_sync(market, symbol, 0, f"ERROR: {err_msg}")
            self._increment_stat("ERROR")

        elif task_type == "SAVE_MAPPING":
            _, s_id, source_tag, mapped_label, model, reasoning, conf = task
            audit_manager.log_mapping(s_id, source_tag, mapped_label, reasoning, conf, model)

        elif task_type == "LOG_SKIP":
            _, market, symbol, reason = task
            logger.info(f"Recording skip for {market}:{symbol} (Reason: {reason})")
            audit_manager.log_ticker_sync(market, symbol, 0, "SKIPPED_NOT_FOUND")

    def _process_jp_bulk_ingest(self, task):
        _, date_str, df, session_id = task
        if "LocalCode" in df.columns:
            code_col = "LocalCode"
        elif "Code" in df.columns:
            code_col = "Code"
        else:
            code_col = "code"

        unique_codes = df[code_col].unique()
        logger.info(
            f"[DBWriter] Ingesting bulk JP data for {len(unique_codes)} tickers from {date_str}..."
        )

        for code in unique_codes:
            ticker_df = df[df[code_col] == code]
            ticker_code = str(code)
            self.jp_engine.ingest_facts(ticker_code, ticker_df, session_id)
            audit_manager.log_ticker_sync("JP", ticker_code, 1, "SUCCESS")
            self._increment_stat("SUCCESS")

    def _ai_mapper_worker(self):
        """【Thread 2: AI Mapper】 未知のタグをキューから受け取り、非同期でGeminiにマッピングさせるスレッド"""
        logger.info("AI Mapper Thread started.")
        while self.is_running:
            try:
                task = self.ai_queue.get(timeout=1.0)
                if task is None:
                    self.ai_queue.task_done()
                    break

                try:
                    task_type = task[0]
                    if task_type == "MAP_TAGS":
                        _, market, symbol, tags_to_map, session_id = task
                        logger.info(f"[AIMapper] Mapping {len(tags_to_map)} tags for {symbol}...")
                        results = self.mapper.map_tags_bulk(market, tags_to_map, session_id)
                        for res in results:
                            self.db_queue.put(
                                (
                                    "SAVE_MAPPING",
                                    session_id,
                                    res["source_tag"],
                                    res["mapped_label"],
                                    res["model"],
                                    res["reasoning"],
                                    res["confidence"],
                                )
                            )
                        logger.info(f"[AIMapper] Finished mapping for {symbol}.")
                except Exception as e:
                    logger.error(f"Error in AI Mapper worker: {e}", exc_info=True)
                finally:
                    self.ai_queue.task_done()
            except queue.Empty:
                continue

    def _increment_stat(self, status: str):
        with self._stats_lock:
            self.session_stats[status] += 1

    def _queue_unmapped_tags(self, market: str, symbol: str, session_id: str):
        """Check for unmapped tags and place them in AI queue (Called securely by DB Writer)."""
        engine = self.us_engine if market == "US" else self.jp_engine
        db_id = symbol
        col_name = "code"
        if market == "US":
            col_name = "cik"
            with duckdb.connect(str(self.us_engine.db_path)) as conn:
                res = conn.execute("SELECT cik FROM tickers WHERE ticker = ?", [symbol]).fetchone()
                if res:
                    db_id = res[0]

        with duckdb.connect(str(engine.db_path)) as conn:
            raw_tags = conn.execute(
                f"SELECT DISTINCT tag, label FROM company_facts WHERE {col_name} = ?", [db_id]
            ).fetchall()

        if not raw_tags:
            return

        source_tags = [f"{market}:{t[0]}" for t in raw_tags]
        unmapped_source = audit_manager.get_unmapped_tags(market, source_tags)

        lookup = {f"{market}:{t[0]}": t for t in raw_tags}
        unmapped_final = [lookup[ut] for ut in unmapped_source]

        if unmapped_final:
            logger.info(
                f"Found {len(unmapped_final)} unmapped tags for {symbol}. Sending to AI Queue."
            )
            tags_to_map = [(tag, label or tag) for tag, label in unmapped_final]
            self.ai_queue.put(("MAP_TAGS", market, symbol, tags_to_map, session_id))

    def wait_for_queues(self):
        """Block until all processing is finished."""
        self.ai_queue.join()
        self.db_queue.join()
        # Double check to ensure AI queue didn't place new tasks into DB queue
        self.ai_queue.join()
        self.db_queue.join()

    def sync_market_full(
        self,
        market: str,
        limit: int | None = None,
        dry_run: bool = False,
        incremental: bool = True,
    ):
        """
        【Thread 3: Data Fetchers】 Orchestrate full market sync.
        Utilizes Fetcher ThreadPool + Message Queues for maximum throughput.
        """
        session_id = audit_manager.start_session(market)
        logger.info(f"Starting {market} sync session: {session_id} (Incremental: {incremental})")
        start_wall_time = time.perf_counter()

        # Reset stats
        with self._stats_lock:
            self.session_stats = {"SUCCESS": 0, "ERROR": 0}

        try:
            if market == "US":
                self._sync_us_market(session_id, limit, dry_run, incremental)
            elif market == "JP":
                self._sync_jp_market(session_id, limit, dry_run, incremental)
            else:
                raise ValueError(f"Unknown market: {market}")

            logger.info(
                f"All {market} network fetch requests completed. Waiting for DB/AI processing..."
            )
            self.wait_for_queues()

            total_duration = time.perf_counter() - start_wall_time
            success_count = self.session_stats["SUCCESS"]
            error_count = self.session_stats["ERROR"]

            audit_manager.end_session(session_id, "SUCCESS", success_count, error_count)

            logger.info("=" * 60)
            logger.info(f"SYNC SESSION COMPLETED: {session_id}")
            logger.info(f"Market: {market} | Duration: {total_duration:.2f}s")
            logger.info(f"Successful Tickers: {success_count}")
            logger.info(f"Failed Tickers:     {error_count}")
            logger.info("=" * 60)

            return success_count, error_count

        except Exception as e:
            logger.error(f"Sync session {session_id} fatal error: {e}", exc_info=True)
            audit_manager.end_session(session_id, "FAILED", 0, 1, str(e))
            raise e

    def _sync_us_market(self, session_id: str, limit: int | None, dry_run: bool, incremental: bool):
        logger.info("Syncing US Ticker list...")
        self.us_engine.sync_tickers(session_id)

        with duckdb.connect(str(self.us_engine.db_path)) as conn:
            all_symbols = [r[0] for r in conn.execute("SELECT ticker FROM tickers").fetchall()]

        synced = audit_manager.get_synced_symbols("US") if incremental else []
        to_sync = [s for s in all_symbols if s not in synced]
        if limit:
            to_sync = to_sync[:limit]

        logger.info(f"Identified {len(to_sync)} US tickers requiring sync.")

        def fetch_worker(ticker):
            if dry_run:
                logger.info(f"DRY RUN: Syncing {ticker}")
                return
            try:
                data = self.us_engine.fetch_company_facts(ticker)
                if data:
                    self.db_queue.put(("US_INGEST", ticker, data, session_id))
                else:
                    logger.info(f"No facts returned for US Ticker {ticker} (Benign).")
                    self.db_queue.put(("LOG_SKIP", "US", ticker, "404 NOT_FOUND"))
            except Exception as e:
                logger.error(f"US Fetch Error ({ticker}): {e}")
                self.db_queue.put(("LOG_ERROR", "US", ticker, str(e)))

        # Network I/O in parallel (Pool acts as multiple producer threads)
        with ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(fetch_worker, to_sync)

    def _sync_jp_market(self, session_id: str, limit: int | None, dry_run: bool, incremental: bool):
        """Sync JP market using optimized date-based bulk fetch."""
        logger.info("Starting JP market sync (Optimized Date-Based Mode)...")

        # 1. Always sync ticker list first to ensure we know what exists
        try:
            self.jp_engine.sync_tickers(session_id)
        except Exception as e:
            logger.warning(f"Failed to sync JP ticker list from API: {e}. Falling back to DB.")

        # 2. Execute High-Speed Date-Based Sync
        # For Free plans, this is 70x faster for bulk data retrieval.
        try:
            self._sync_jp_market_by_date(session_id, dry_run=dry_run)
            logger.info("Completed JP Date-Based Optimized Sync Pass.")
        except Exception as e:
            logger.error(f"Critical error in JP Date-Based Sync: {e}", exc_info=True)

    def _sync_jp_market_by_date(self, session_id: str, dry_run: bool = False):
        """Fetch all available JP disclosures day-by-day (optimized for 5 req/min limit)."""
        # Free plan has a 12-week window (~84 days). We scan 90 days to be thorough.
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=90)

        current_date = start_date
        logger.info(f"Scanning JP disclosures from {start_date} to {end_date} (Bulk Date Mode)")

        while current_date <= end_date:
            # Skip weekends
            weekend_start_idx = 5
            if current_date.weekday() < weekend_start_idx:
                date_str = current_date.strftime("%Y-%m-%d")

                if dry_run:
                    logger.info(f"DRY RUN: Would fetch JP data for date {date_str}")
                else:
                    try:
                        # STRICT RATE LIMIT: 12.5s per request (Free Plan: 5 req/min)
                        msg = f"Fetching JP disclosures for {date_str} (Respecting rate limits)..."
                        logger.info(msg)
                        time.sleep(12.5)

                        df = self.jp_engine.cli.get_fin_summary(
                            date_yyyymmdd=date_str.replace("-", "")
                        )

                        if df is not None and not df.empty:
                            msg = f"Received {len(df)} disclosures for {date_str}. Sending to DB..."
                            logger.info(msg)
                            self.db_queue.put(("JP_INGEST_BULK", date_str, df, session_id))
                        else:
                            logger.info(f"No disclosures found for {date_str}.")

                    except Exception as e:
                        err_str = str(e)
                        if (
                            "403" in err_str
                            or "subscription" in err_str.lower()
                            or "400" in err_str
                        ):
                            msg = f"Date {date_str} is outside of subscription plan. Skipping."
                            logger.debug(msg)
                        elif "429" in err_str:
                            logger.warning(
                                f"Rate limit exceeded for {date_str}. Cooling down for 60s..."
                            )
                            time.sleep(60)
                            continue  # Retry the same date
                        else:
                            logger.error(f"Error fetching JP data for {date_str}: {e}")

            current_date += datetime.timedelta(days=1)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    service = BatchSyncService()
    service.sync_market_full("US", limit=5)
    service.sync_market_full("JP", limit=5)
    service.stop()
