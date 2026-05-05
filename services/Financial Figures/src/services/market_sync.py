import datetime
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from loguru import logger

from src.core.audit_manager import audit_manager
from src.core.config import settings
from src.core.db import db_manager
from src.core.logging import track_performance
from src.engines.jp_engine import JPEngine
from src.engines.us_engine import USEngine
from src.mappers.ai_mapper import AIMapper


class BatchSyncService:
    def __init__(self, start_workers: bool = True):
        self.us_engine = USEngine()
        self.jp_engine = JPEngine()
        self.mapper = AIMapper()
        audit_manager._init_db()

        # Segregated Queues
        self.us_db_queue = queue.Queue(maxsize=settings.SYNC_QUEUE_MAXSIZE)
        self.jp_db_queue = queue.Queue(maxsize=settings.SYNC_QUEUE_MAXSIZE)
        self.audit_db_queue = queue.Queue(maxsize=settings.SYNC_QUEUE_MAXSIZE)
        self.ai_queue = queue.Queue(maxsize=settings.SYNC_QUEUE_MAXSIZE)

        self.is_running = True
        self._stats_lock = threading.Lock()
        self.session_stats = {"SUCCESS": 0, "ERROR": 0}

        self.workers = {}
        if start_workers:
            self._start_workers()

    def _start_workers(self):
        configs = [
            ("US_Writer", self.us_db_queue, self._us_writer_worker),
            ("JP_Writer", self.jp_db_queue, self._jp_writer_worker),
            ("Audit_Writer", self.audit_db_queue, self._audit_writer_worker),
            ("AI_Mapper", self.ai_queue, self._ai_mapper_worker),
        ]
        for _name, q, target in configs:
            t = threading.Thread(target=target, daemon=True, name=_name)
            t.start()
            self.workers[_name] = (t, q)

    def stop(self):
        logger.info("Stopping BatchSyncService...")
        self.is_running = False
        self.mapper.shutdown(wait=False)
        for _, q in self.workers.values():
            q.put(None)
        for _name, (t, _) in self.workers.items():
            if t.is_alive():
                t.join(timeout=5.0)
        logger.info("BatchSyncService stopped.")

    def _us_writer_worker(self):
        while self.is_running:
            task = self.us_db_queue.get()
            if task is None:
                break
            try:
                _, ticker, data, session_id = task
                self.us_engine.ingest_facts(ticker, data, session_id)
                self.audit_db_queue.put(("TICKER_SYNC", "US", ticker, 1, "SUCCESS"))
                self._increment_stat("SUCCESS")
                self._queue_unmapped_tags("US", ticker, session_id)
            except Exception as e:
                ticker_label = ticker if 'ticker' in locals() else 'unknown'
                logger.error(f"US Writer error for {ticker_label}: {e}")
                self._increment_stat("ERROR")
            finally:
                self.us_db_queue.task_done()

    def _jp_writer_worker(self):
        while self.is_running:
            task = self.jp_db_queue.get()
            if task is None:
                break
            try:
                task_type = task[0]
                if task_type == "JP_INGEST":
                    _, code, df, session_id = task
                    self.jp_engine.ingest_facts(code, df, session_id)
                    self._queue_unmapped_tags("JP", code, session_id)
                elif task_type == "JP_BULK":
                    _, _date_str, df, session_id = task
                    code_col = "LocalCode" if "LocalCode" in df.columns else "Code"
                    for code in df[code_col].unique():
                        self.jp_engine.ingest_facts(
                            str(code), df[df[code_col] == code], session_id
                        )
                        self._queue_unmapped_tags("JP", str(code), session_id)
                self.audit_db_queue.put(("TICKER_SYNC", "JP", "bulk", 1, "SUCCESS"))
                self._increment_stat("SUCCESS")
            except Exception as e:
                logger.error(f"JP Writer error: {e}")
                self._increment_stat("ERROR")
            finally:
                self.jp_db_queue.task_done()

    def _audit_writer_worker(self):
        while self.is_running:
            task = self.audit_db_queue.get()
            if task is None:
                break
            try:
                if task[0] == "TICKER_SYNC":
                    _, m, sym, count, status = task
                    audit_manager.log_ticker_sync(m, sym, count, status)
                elif task[0] == "SAVE_MAPPING":
                    _, s_id, tag, label, model, reason, conf = task
                    audit_manager.log_mapping(s_id, tag, label, reason, conf, model)
            except Exception as e:
                logger.error(f"Audit Writer error: {e}")
            finally:
                self.audit_db_queue.task_done()

    def _ai_mapper_worker(self):
        while self.is_running:
            task = self.ai_queue.get()
            if task is None:
                break
            try:
                _, market, symbol, tags, s_id = task
                logger.info(f"AI Mapping task for {symbol} ({len(tags)} tags)")
                results = self.mapper.map_tags_bulk(market, tags, s_id)
                for res in results:
                    self.audit_db_queue.put(
                        (
                            "SAVE_MAPPING",
                            s_id,
                            res["source_tag"],
                            res["mapped_label"],
                            res["model"],
                            res["reasoning"],
                            res["confidence"]
                        )
                    )
            except Exception as e:
                logger.error(f"AI Mapper worker error: {e}")
            finally:
                self.ai_queue.task_done()

    def _increment_stat(self, status: str):
        with self._stats_lock:
            self.session_stats[status] += 1

    @track_performance("queue_unmapped_tags")
    def _queue_unmapped_tags(self, market: str, symbol: str, session_id: str):
        """Check for unmapped tags and place them in AI queue."""
        try:
            engine = self.us_engine if market == "US" else self.jp_engine
            db_id = symbol
            if market == "US":
                with db_manager.connect(self.us_engine.db_path, read_only=True) as conn:
                    res = conn.execute(
                        "SELECT cik FROM tickers WHERE ticker = ?", [symbol]
                    ).fetchone()
                    if res:
                        db_id = res[0]

                query = "SELECT DISTINCT tag, label FROM company_facts WHERE cik = ?"
                with db_manager.connect(engine.db_path, read_only=True) as conn:
                    raw_tags = conn.execute(query, [db_id]).fetchall()
                if not raw_tags:
                    return
                source_tags = [f"{market}:{t[0]}" for t in raw_tags]
                lookup = {f"{market}:{t[0]}": t for t in raw_tags}
            else:
                # Wide format for JP: Get column names that are financial metrics
                with db_manager.connect(engine.db_path, read_only=True) as conn:
                    # Get schema to find numeric columns
                    cols = conn.execute("PRAGMA table_info('company_facts')").fetchall()
                    # Skip metadata columns
                    skip = {
                        "DisclosedDate",
                        "DisclosedTime",
                        "LocalCode",
                        "DisclosureNumber",
                        "Type",
                        "FiscalYear",
                        "FiscalPeriod",
                        "session_id",
                        "ingested_at",
                    }
                    raw_tags = [(c[1], c[1]) for c in cols if c[1] not in skip]
                if not raw_tags:
                    return
                source_tags = [f"{market}:{t[0]}" for t in raw_tags]
                lookup = {f"{market}:{t[0]}": t for t in raw_tags}

            unmapped_source = audit_manager.get_unmapped_tags(market, source_tags)
            unmapped_final = [lookup[ut] for ut in unmapped_source]

            if unmapped_final:
                tags_to_map = [(tag, label or tag) for tag, label in unmapped_final]
                self.ai_queue.put(("MAP_TAGS", market, symbol, tags_to_map, session_id))
        except Exception as e:
            logger.error(f"Error queuing unmapped tags for {symbol}: {e}")
            # Non-critical, so we don't raise

    def wait_for_queues(self):
        logger.info("Waiting for queues to empty...")
        for name, q in self.workers.items():
            logger.info(f"  Waiting for {name} queue...")
            q.join()
        logger.info("All queues joined.")

    @track_performance("sync_market_full")
    def sync_market_full(
        self,
        market: str,
        limit: int | None = None,
        dry_run: bool = False,
        incremental: bool = True
    ):
        session_id = audit_manager.start_session(market)
        logger.info(f"Started full market sync for {market} (Session: {session_id})")
        try:
            if market == "US":
                self._sync_us_market(session_id, limit, dry_run, incremental)
            elif market == "JP":
                self._sync_jp_market(session_id, limit, dry_run, incremental)
            self.wait_for_queues()
            audit_manager.end_session(
                session_id, "SUCCESS", self.session_stats["SUCCESS"], self.session_stats["ERROR"]
            )
            logger.info(
                f"Sync complete for {market}. "
                f"Success: {self.session_stats['SUCCESS']}, Errors: {self.session_stats['ERROR']}"
            )
        except Exception as e:
            logger.error(f"Sync failed for {market}: {e}")
            audit_manager.end_session(session_id, "FAILED", 0, 1, str(e))
            raise

    @track_performance("sync_us_market_batch")
    def _sync_us_market(self, session_id, limit, dry_run, incremental):
        self.us_engine.sync_tickers(session_id)
        with db_manager.connect(self.us_engine.db_path, read_only=True) as conn:
            all_symbols = [r[0] for r in conn.execute("SELECT ticker FROM tickers").fetchall()]

        synced_symbols = audit_manager.get_synced_symbols("US") if incremental else []
        to_sync = [s for s in all_symbols if s not in synced_symbols]

        if limit:
            to_sync = to_sync[:limit]

        logger.info(f"Queuing {len(to_sync)} US tickers for sync...")

        def worker(ticker):
            try:
                data = self.us_engine.fetch_company_facts(ticker)
                if data:
                    self.us_db_queue.put(("US_INGEST", ticker, data, session_id))
                else:
                    logger.info(f"No facts returned for US Ticker {ticker} (Benign).")
            except Exception as e:
                logger.error(f"US Fetch Error ({ticker}): {e}")
                self.audit_db_queue.put(("TICKER_SYNC", "US", ticker, 0, f"ERROR: {e!s}"))
                self._increment_stat("ERROR")

        with ThreadPoolExecutor(max_workers=5) as exec_pool:
            exec_pool.map(worker, to_sync)

    @track_performance("sync_jp_market_batch")
    def _sync_jp_market(self, session_id, limit, dry_run, incremental):
        self.jp_engine.sync_tickers(session_id)
        # J-Quants Free Plan: 12-week (84 days) delay
        # We start syncing from (today - 84 days) going backwards to (today - 84 - 90 days)
        delay_days = 84
        sync_range = 90
        base_date = datetime.date.today() - datetime.timedelta(days=delay_days)
        logger.info(
            f"Fetching JP financial summaries for Free Plan (Window: {base_date} backwards)..."
        )
        for i in range(sync_range):
            d = base_date - datetime.timedelta(days=i)
            if d.weekday() < 5:
                try:
                    # V2 API uses date_yyyymmdd
                    df = self.jp_engine.cli.get_fin_summary(date_yyyymmdd=d.strftime("%Y%m%d"))
                    if df is not None and not df.empty:
                        logger.info(
                            f"Queuing JP summary for {d.strftime('%Y-%m-%d')} ({len(df)} records)"
                        )
                        self.jp_db_queue.put(("JP_BULK", d.strftime("%Y-%m-%d"), df, session_id))
                    else:
                        logger.debug(f"No JP summary found for {d.strftime('%Y-%m-%d')}")
                except Exception as e:
                    if "400" in str(e) and "subscription" in str(e).lower():
                        logger.warning(f"J-Quants limit reached for {d}: {e}")
                    else:
                        logger.error(f"Error fetching JP summary for {d.strftime('%Y-%m-%d')}: {e}")

                # J-Quants Rate Limit: Be respectful
                time.sleep(1.2)

