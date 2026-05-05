import random
import sqlite3
import time
from pathlib import Path
from typing import Any

from loguru import logger


class JobQueue:
    """
    State-Based Orchestration のためのマスターコントロールプレーン。
    SQLiteを使用して、LLM推論 (構造化) タスクのステータスをアトミックに管理する。
    """

    def __init__(self, db_path: str = "data/sync_master.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    accession_number TEXT PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    market TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    retry_count INTEGER DEFAULT 0,
                    result_json TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # ステータス検索を高速化するインデックス
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)")
            conn.commit()

    def _execute_with_retry(self, query: str, params: tuple = (), commit: bool = True):
        """SQLiteのロック競合時に自動リトライするヘルパー"""
        for attempt in range(10):
            try:
                with sqlite3.connect(str(self.db_path), timeout=30.0) as conn:
                    conn.row_factory = sqlite3.Row
                    # 高速化・並列耐性向上のための設定
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.execute("PRAGMA synchronous=NORMAL")
                    cursor = conn.execute(query, params)
                    if commit:
                        conn.commit()
                    return cursor
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower():
                    wait_time = (2**attempt) * 0.1 + random.uniform(0, 0.2)
                    time.sleep(wait_time)
                    continue
                logger.error(f"SQL OperationalError: {e} | Query: {query}")
                raise e
            except Exception as e:
                logger.error(f"SQL Error: {e} | Query: {query}")
                raise e
        raise RuntimeError(f"Database locked for too long: {query}")

    def enqueue_job(self, accession_number: str, ticker: str, market: str) -> bool:
        """未処理のジョブをキューに登録する。"""
        try:
            query = """
                INSERT INTO jobs (accession_number, ticker, market, status)
                VALUES (?, ?, ?, 'PENDING')
                ON CONFLICT(accession_number) DO UPDATE SET
                    status = 'PENDING',
                    retry_count = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE status IN ('COMPLETED', 'FAILED')
            """
            cursor = self._execute_with_retry(query, (accession_number, ticker, market))
            return cursor.rowcount > 0
        except Exception:
            logger.exception(f"Unexpected error enqueuing job | acc_no={accession_number}")
            return False

    def dequeue_job(self, market: str | None = None) -> dict[str, Any] | None:
        """アトミックに未処理のジョブを取得。market指定がある場合はフィルタリングする。"""
        try:
            market_filter = "AND market = ?" if market else ""
            params = [market] if market else []

            for attempt in range(10):
                try:
                    with sqlite3.connect(str(self.db_path), timeout=30.0) as conn:
                        conn.row_factory = sqlite3.Row
                        cursor = conn.execute(
                            f"""
                            UPDATE jobs
                            SET status = 'PROCESSING', updated_at = CURRENT_TIMESTAMP
                            WHERE accession_number = (
                                SELECT accession_number
                                FROM jobs
                                WHERE (status = 'PENDING' OR (status = 'FAILED' AND retry_count < 3))
                                {market_filter}
                                ORDER BY created_at ASC
                                LIMIT 1
                            )
                            RETURNING accession_number, ticker, market, retry_count
                        """,
                            params,
                        )
                        row = cursor.fetchone()
                        conn.commit()
                        return dict(row) if row else None
                except sqlite3.OperationalError as e:
                    if "locked" in str(e).lower():
                        wait_time = (2**attempt) * 0.1 + random.uniform(0, 0.1)
                        time.sleep(wait_time)
                        continue
                    raise e
            return None
        except Exception:
            logger.exception("Error during dequeue_job")
            return None

    def complete_job(self, accession_number: str):
        """ジョブの完了を記録する"""
        query = """
            UPDATE jobs
            SET status = 'COMPLETED', updated_at = CURRENT_TIMESTAMP, error_message = NULL
            WHERE accession_number = ?
        """
        self._execute_with_retry(query, (accession_number,))

    def fail_job(self, accession_number: str, error_message: str):
        """ジョブの失敗を記録し、リトライ回数を増やす"""
        query = """
            UPDATE jobs
            SET status = 'FAILED',
                retry_count = retry_count + 1,
                error_message = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE accession_number = ?
        """
        self._execute_with_retry(query, (str(error_message), accession_number))

    def update_job_status(self, accession_number: str, status: str, worker_info: str = None):
        """ジョブのステータスを詳細に更新する"""
        if worker_info:
            query = """
                UPDATE jobs
                SET status = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE accession_number = ?
            """
            self._execute_with_retry(
                query, (status, f"Worker: {worker_info}", accession_number)
            )
        else:
            query = """
                UPDATE jobs
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE accession_number = ?
            """
            self._execute_with_retry(query, (status, accession_number))

    def store_parsed_result(self, accession_number: str, result_json: str):
        """解析結果を一時保存し、Writerの処理待ちにする"""
        query = """
            UPDATE jobs
            SET status = 'PARSED',
                result_json = ?,
                updated_at = CURRENT_TIMESTAMP,
                error_message = NULL
            WHERE accession_number = ?
        """
        self._execute_with_retry(query, (result_json, accession_number))

    def get_parsed_jobs(self, limit: int = 50) -> list[dict]:
        """Writerが処理すべき解析済みジョブを取得する"""
        query = """
            SELECT * FROM jobs
            WHERE status = 'PARSED'
            ORDER BY updated_at ASC
            LIMIT ?
        """
        cursor = self._execute_with_retry(query, (limit,), commit=False)
        return [dict(row) for row in cursor.fetchall()]

    def force_reset_active_jobs(self):
        """システム起動時、未完了のすべてのアクティブジョブを 'PENDING' に戻す"""
        try:
            query = """
                UPDATE jobs
                SET status = 'PENDING', updated_at = CURRENT_TIMESTAMP, error_message = 'Restart reset'
                WHERE status IN ('PROCESSING', 'FETCHING', 'LLM_WAITING', 'SAVING')
            """
            cursor = self._execute_with_retry(query)
            if cursor.rowcount > 0:
                logger.info(f"Forcefully reset {cursor.rowcount} active jobs to PENDING.")
        except Exception:
            logger.exception("Failed to force reset active jobs")

    def cleanup_zombie_jobs(self, timeout_minutes: int = 60):
        """長時間停滞しているジョブを 'PENDING' に戻す"""
        try:
            query = """
                UPDATE jobs
                SET status = 'PENDING', updated_at = CURRENT_TIMESTAMP, error_message = 'Zombie cleanup'
                WHERE status IN ('PROCESSING', 'FETCHING', 'LLM_WAITING', 'SAVING')
                AND datetime(updated_at, 'localtime') < datetime('now', 'localtime', ?)
            """
            cursor = self._execute_with_retry(query, (f"-{timeout_minutes} minutes",))
            if cursor.rowcount > 0:
                logger.warning(f"Reset {cursor.rowcount} zombie jobs back to PENDING")
        except Exception:
            logger.exception("Failed to cleanup zombie jobs")

    def get_stats(self) -> dict[str, int]:
        """キューの状態を取得する"""
        try:
            cursor = self._execute_with_retry(
                "SELECT status, COUNT(*) FROM jobs GROUP BY status", commit=False
            )
            rows = cursor.fetchall()
            stats = {row[0]: row[1] for row in rows}
            for state in ["PENDING", "PROCESSING", "COMPLETED", "FAILED", "PARSED"]:
                if state not in stats:
                    stats[state] = 0
            return stats
        except Exception:
            logger.exception("Failed to get stats")
            return {}
