import queue
import threading

import zstandard as zstd
from loguru import logger

from src.shared.infra.config import settings
from src.shared.infra.db import db_manager


class DatabaseWriter:
    """
    Serialized Database Writer.
    Consumes results from a queue and writes them to DuckDB in batches.
    This prevents contention by ensuring only one thread/process handles writes
    at a specific time, and analysis happens outside the lock.
    """

    def __init__(self, batch_size=250):
        self.queue = queue.Queue()
        self.batch_size = batch_size
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        """Starts the background writer thread."""
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="DBWriterThread", daemon=True)
        self._thread.start()
        logger.info("Database Writer Thread started.")

    def stop(self):
        """Signals the writer thread to stop and waits for completion."""
        self._stop_event.set()
        if self._thread:
            self._thread.join()
            self._thread = None
        self._stop_event.clear()
        logger.info("Database Writer Thread stopped.")

    def put(self, result_type, data):
        """Adds a task to the queue. result_type can be 'ingest' or 'log'."""
        self.queue.put((result_type, data))

    def _run(self):
        results_batch = []
        logs_batch = []

        logger.debug("Opening persistent connection for DatabaseWriter...")
        try:
            with db_manager.connect_master() as conn:
                while not self._stop_event.is_set() or not self.queue.empty():
                    try:
                        # Wait for data with a timeout to check stop_event
                        item = self.queue.get(timeout=1.0)
                        res_type, data = item

                        if res_type == "ingest":
                            results_batch.append(data)
                        elif res_type == "log":
                            logs_batch.append(data)

                        # Flush if batch size reached
                        if (
                            len(results_batch) >= self.batch_size
                            or len(logs_batch) >= self.batch_size
                        ):
                            self._flush_internal(conn, results_batch, logs_batch)
                            results_batch.clear()
                            logs_batch.clear()

                        self.queue.task_done()
                    except queue.Empty:
                        # Flush remaining if empty for a while
                        if results_batch or logs_batch:
                            self._flush_internal(conn, results_batch, logs_batch)
                            results_batch.clear()
                            logs_batch.clear()
                        continue
                    except Exception as e:
                        logger.error(f"Error in DB Writer item processing: {e}", exc_info=True)

                # Final flush
                if results_batch or logs_batch:
                    self._flush_internal(conn, results_batch, logs_batch)
        except Exception as e:
            logger.critical(
                f"Fatal error in DB Writer thread (connection lost): {e}", exc_info=True
            )

    def _flush_internal(self, conn, results, logs):
        if not results and not logs:
            return

        logger.info(f"Writer flushing {len(results)} results and {len(logs)} logs to DB...")
        try:
            if results:
                self._flush_results_to_db(conn, results)
            if logs:
                self._update_ingestion_logs(conn, logs)
        except Exception as e:
            logger.error(f"Failure during internal DB flush: {e}", exc_info=True)
            # We don't raise here to keep the writer thread alive if possible

    def _flush_results_to_db(self, conn, results):
        # Implementation moved from DataIngestor to centralize write logic
        metadata_batch = [
            (
                r["metadata"]["doc_id"],
                r["metadata"]["edinet_code"],
                r["metadata"]["sec_code"],
                r["metadata"]["filer_name"],
                r["metadata"]["doc_description"],
                r["metadata"]["submit_datetime"],
                r["metadata"]["form_code"],
                r["metadata"]["doc_type_code"],
                r["metadata"]["session_id"],
            )
            for r in results
        ]

        logger.debug(f"Inserting {len(metadata_batch)} metadata records.")
        self._batch_insert_resilient(
            conn,
            "INSERT OR IGNORE INTO registry_db.filings (doc_id, edinet_code, sec_code, filer_name, "
            "doc_description, submit_datetime, form_code, doc_type_code, session_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            metadata_batch,
        )

        narrative_batch = []
        cctx = zstd.ZstdCompressor(level=settings.ZSTD_COMPRESSION_LEVEL)

        for r in results:
            for n in r["narratives"]:
                compressed_content = cctx.compress(n["content_md"].encode("utf-8"))
                narrative_batch.append(
                    (n["doc_id"], n["section_name"], compressed_content, n["session_id"])
                )

        if narrative_batch:
            logger.debug(f"Inserting {len(narrative_batch)} compressed narrative records.")
            self._batch_insert_resilient(
                conn,
                "INSERT OR REPLACE INTO narr_db.narratives (doc_id, section_name, content_md, "
                "session_id) VALUES (?, ?, ?, ?)",
                narrative_batch,
            )

        fact_batch = [
            (
                f["doc_id"],
                f["item_name"],
                f["item_value"],
                f["unit"],
                f["context_id"],
                f["fiscal_year"],
                f["fiscal_period"],
                f["session_id"],
            )
            for r in results
            for f in r["facts"]
        ]

        if fact_batch:
            logger.debug(f"Inserting {len(fact_batch)} fact records.")
            self._batch_insert_resilient(
                conn,
                "INSERT OR REPLACE INTO facts_db.company_facts (doc_id, item_name, item_value, "
                "unit, context_id, fiscal_year, fiscal_period, session_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                fact_batch,
            )

    def _batch_insert_resilient(self, conn, sql, batch):
        try:
            conn.executemany(sql, batch)
        except Exception as batch_err:
            logger.warning(f"Batch insert failed, falling back to individual inserts: {batch_err}")
            for record in batch:
                try:
                    conn.execute(sql, record)
                except Exception as rec_err:
                    logger.error(
                        f"Isolated failure for doc_id {record[0]}: {rec_err}",
                        extra={"record": record},
                    )

    def _update_ingestion_logs(self, conn, logs):
        sql = """
            INSERT INTO ingestion_log (doc_id, status, last_attempt, error_message, retry_count)
            VALUES (?, ?, ?, ?, 0)
            ON CONFLICT (doc_id) DO UPDATE SET
                status = excluded.status,
                last_attempt = excluded.last_attempt,
                error_message = excluded.error_message,
                retry_count = retry_count + 1
        """
        conn.executemany(sql, logs)


class RawCacheWriter:
    """
    Asynchronous Writer for Zstandard raw data compression.
    Consumes raw bytes from a queue and compresses/writes them to disk.
    This prevents CPU-intensive compression from blocking the main ingestion threads.
    """

    def __init__(self):
        self.queue = queue.Queue()
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="RawCacheWriterThread", daemon=True)
        self._thread.start()
        logger.info("Raw Cache Writer Thread started.")

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join()
            self._thread = None
        self._stop_event.clear()
        logger.info("Raw Cache Writer Thread stopped.")

    def put(self, doc_id: str, content: bytes):
        self.queue.put((doc_id, content))

    def _run(self):
        while not self._stop_event.is_set() or not self.queue.empty():
            try:
                item = self.queue.get(timeout=1.0)
                doc_id, content = item

                cache_path = settings.RAW_DATA_DIR / f"{doc_id}_csv.zip.zst"
                try:
                    cctx = zstd.ZstdCompressor(level=settings.ZSTD_COMPRESSION_LEVEL)
                    with open(cache_path, "wb") as f:
                        f.write(cctx.compress(content))
                    logger.debug(
                        f"Async cached raw CSV for {doc_id} to {cache_path} "
                        f"(level {settings.ZSTD_COMPRESSION_LEVEL})"
                    )
                except Exception as e:
                    logger.warning(f"Failed to async cache raw CSV for {doc_id}: {e}")

                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in Raw Cache Writer thread: {e}", exc_info=True)
