import json
import sqlite3
from pathlib import Path

from loguru import logger

from src.config import MASTER_DB_PATH


class JobQueue:
    """
    SQLiteを使用したジョブキュー管理クラス
    - PENDING (0): 待機中
    - PROCESSING (1): 処理中
    - COMPLETED (2): 完了
    - FAILED (3): 失敗
    """

    def __init__(self):
        self.db_path = MASTER_DB_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS structuring_jobs (
                    accession_number TEXT PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    market TEXT NOT NULL,
                    status INTEGER DEFAULT 0,
                    retry_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            # インデックスの作成
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_status ON structuring_jobs(status)"
            )

    def enqueue_job(self, accession_number: str, ticker: str, market: str):
        """未処理のジョブを追加する (既に存在する場合は無視)"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO structuring_jobs (accession_number, ticker, market, status)
                VALUES (?, ?, ?, 0)
            """,
                (accession_number, ticker.upper(), market.lower()),
            )

    def dequeue_job(self) -> dict | None:
        """PENDINGなジョブを1つ取得し、PROCESSINGに変更する (アトミック)"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # ステータスを更新しつつ、更新された行を特定する (SQLiteでは直接できないため、SELECT FOR UPDATEに近い挙動を模倣)
            # シンプルに1件取得して、そのIDでステータスを更新する
            res = cursor.execute(
                "SELECT * FROM structuring_jobs WHERE status = 0 ORDER BY created_at ASC LIMIT 1"
            ).fetchone()

            if res:
                acc_no = res["accession_number"]
                cursor.execute(
                    "UPDATE structuring_jobs SET status = 1, updated_at = CURRENT_TIMESTAMP WHERE accession_number = ?",
                    (acc_no,),
                )
                return dict(res)
            return None

    def complete_job(self, accession_number: str):
        """ジョブを完了状態にする"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE structuring_jobs SET status = 2, updated_at = CURRENT_TIMESTAMP WHERE accession_number = ?",
                (accession_number,),
            )

    def fail_job(self, accession_number: str, error: str):
        """ジョブを失敗状態にする（リトライ回数をインクリメント）"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE structuring_jobs 
                SET status = CASE WHEN retry_count < 3 THEN 0 ELSE 3 END,
                    retry_count = retry_count + 1,
                    error_message = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE accession_number = ?
            """,
                (error, accession_number),
            )

    def get_stats(self):
        with sqlite3.connect(self.db_path) as conn:
            res = conn.execute(
                "SELECT status, COUNT(*) FROM structuring_jobs GROUP BY status"
            ).fetchall()
            return dict(res)

    def mark_job_completed(self, accession_number: str):
        """
        強制的に完了状態にする（Reconcilerで使用）
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE structuring_jobs SET status = 2, updated_at = CURRENT_TIMESTAMP WHERE accession_number = ?",
                (accession_number,),
            )
            logger.info(f"Marked {accession_number} as COMPLETED in SQLite")

    def cleanup_zombie_jobs(self, timeout_minutes: int = 30):
        """
        一定時間以上 PROCESSING のままのジョブを PENDING に戻す。
        クラッシュしたワーカーのタスクを復旧させるための自己修復機能。
        """
        with sqlite3.connect(self.db_path) as conn:
            # updated_at が古い PROCESSING ジョブを特定
            query = """
                UPDATE structuring_jobs
                SET status = 0, updated_at = CURRENT_TIMESTAMP
                WHERE status = 1 
                AND (strftime('%s', 'now') - strftime('%s', updated_at)) > ?
            """
            cursor = conn.execute(query, (timeout_minutes * 60,))
            if cursor.rowcount > 0:
                logger.warning(f"Recovered {cursor.rowcount} zombie jobs (stuck in PROCESSING)")
