import sqlite3
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
            conn.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    accession_number TEXT PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    market TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    retry_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # ステータス検索を高速化するインデックス
            conn.execute('CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)')
            conn.commit()

    def enqueue_job(self, accession_number: str, ticker: str, market: str) -> bool:
        """
        未処理のジョブをキューに登録する。
        既に存在する場合、ステータスが 'COMPLETED' または 'FAILED' であれば 'PENDING' にリセット。
        'PROCESSING' の場合は、現在実行中であるため上書きしない。
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                # UPSERT (INSERT ... ON CONFLICT) を使用
                cursor = conn.execute('''
                    INSERT INTO jobs (accession_number, ticker, market, status)
                    VALUES (?, ?, ?, 'PENDING')
                    ON CONFLICT(accession_number) DO UPDATE SET
                        status = 'PENDING',
                        retry_count = 0,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE status IN ('COMPLETED', 'FAILED')
                ''', (accession_number, ticker, market))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to enqueue job {accession_number}: {e}")
            return False

    def dequeue_job(self) -> dict[str, Any] | None:
        """
        アトミックに未処理のジョブを1つ取得し、ステータスを 'PROCESSING' に変更する。
        これにより、複数の並列ワーカーが同じジョブを取るのを防ぐ (Double Execution Prevention)。
        """
        # SQLite 3.35.0+ の UPDATE ... RETURNING を使用して、アトミックに取得と更新を行う。
        try:
            with sqlite3.connect(str(self.db_path), timeout=30.0) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    UPDATE jobs
                    SET status = 'PROCESSING', updated_at = CURRENT_TIMESTAMP
                    WHERE accession_number = (
                        SELECT accession_number
                        FROM jobs
                        WHERE status = 'PENDING' OR (status = 'FAILED' AND retry_count < 3)
                        ORDER BY created_at ASC
                        LIMIT 1
                    )
                    RETURNING accession_number, ticker, market, retry_count
                ''')
                row = cursor.fetchone()
                conn.commit()

                if not row:
                    return None

                return dict(row)
        except Exception as e:
            # 他のプロセス/スレッドがロックしている場合は None を返してリトライを待つ
            if "locked" in str(e).lower():
                return None
            logger.error(f"Error dequeuing job: {e}")
            return None

    def complete_job(self, accession_number: str):
        """ジョブの完了を記録する"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute('''
                UPDATE jobs
                SET status = 'COMPLETED', updated_at = CURRENT_TIMESTAMP, error_message = NULL
                WHERE accession_number = ?
            ''', (accession_number,))
            conn.commit()

    def fail_job(self, accession_number: str, error_message: str):
        """ジョブの失敗を記録し、リトライ回数を増やす"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute('''
                UPDATE jobs
                SET status = 'FAILED',
                    retry_count = retry_count + 1,
                    error_message = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE accession_number = ?
            ''', (str(error_message), accession_number))
            conn.commit()

    def update_job_status(self, accession_number: str, status: str, worker_info: str = None):
        """ジョブのステータスを詳細に更新する (可観測性の向上)"""
        with sqlite3.connect(str(self.db_path)) as conn:
            if worker_info:
                conn.execute('''
                    UPDATE jobs
                    SET status = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE accession_number = ?
                ''', (status, f"Worker: {worker_info}", accession_number))
            else:
                conn.execute('''
                    UPDATE jobs
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE accession_number = ?
                ''', (status, accession_number))
            conn.commit()

    def cleanup_zombie_jobs(self, timeout_minutes: int = 60):
        """長時間 'PROCESSING' 系のまま停滞しているジョブを 'PENDING' に戻す"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                # 'PROCESSING' で始まる詳細ステータスも含めてリセット
                cursor = conn.execute('''
                    UPDATE jobs
                    SET status = 'PENDING', updated_at = CURRENT_TIMESTAMP, error_message = 'Zombie cleanup'
                    WHERE status IN ('PROCESSING', 'FETCHING', 'LLM_WAITING', 'SAVING')
                    AND datetime(updated_at, 'localtime') < datetime('now', 'localtime', ?)
                ''', (f'-{timeout_minutes} minutes',))
                count = cursor.rowcount
                if count > 0:
                    logger.warning(f"Reset {count} zombie jobs back to PENDING")
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to cleanup zombie jobs: {e}")

    def get_stats(self) -> dict[str, int]:
        """キューの状態を取得する"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT status, COUNT(*) FROM jobs GROUP BY status')
            rows = cursor.fetchall()
            stats = {row[0]: row[1] for row in rows}
            # 未定義のステータスは0埋め
            for state in ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']:
                if state not in stats:
                    stats[state] = 0
            return stats
