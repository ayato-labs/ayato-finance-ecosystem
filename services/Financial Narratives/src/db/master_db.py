import sqlite3
import os
from datetime import datetime
from loguru import logger
from typing import Optional, Dict, Any

class JobQueue:
    """
    State-Based Orchestration のためのマスターコントロールプレーン。
    SQLiteを使用して、LLM推論（構造化）タスクのステータスをアトミックに管理する。
    """
    
    def __init__(self, db_path: str = "data/sync_master.sqlite"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
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
        既に存在する場合（再起動時など）は無視する（INSERT OR IGNORE）。
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    INSERT OR IGNORE INTO jobs (accession_number, ticker, market, status)
                    VALUES (?, ?, ?, 'PENDING')
                ''', (accession_number, ticker, market))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to enqueue job {accession_number}: {e}")
            return False

    def dequeue_job(self) -> Optional[Dict[str, Any]]:
        """
        アトミックに未処理のジョブを1つ取得し、ステータスを 'PROCESSING' に変更する。
        これにより、複数の並列ワーカーが同じジョブを取るのを防ぐ (Double Execution Prevention)。
        """
        # SQLite では UPDATE ... RETURNING が 3.35.0 から使用可能。
        # 互換性のためトランザクションと rowid を使う方式をとる。
        with sqlite3.connect(self.db_path, isolation_level='IMMEDIATE') as conn:
            cursor = conn.cursor()
            
            # PENDING または リトライ可能な FAILED を探す (最大3回まで)
            cursor.execute('''
                SELECT accession_number, ticker, market, retry_count 
                FROM jobs 
                WHERE status = 'PENDING' OR (status = 'FAILED' AND retry_count < 3)
                ORDER BY created_at ASC 
                LIMIT 1
            ''')
            row = cursor.fetchone()
            
            if not row:
                return None
                
            acc_no, ticker, market, retry_count = row
            
            # ロック（ステータス更新）
            cursor.execute('''
                UPDATE jobs 
                SET status = 'PROCESSING', updated_at = CURRENT_TIMESTAMP
                WHERE accession_number = ?
            ''', (acc_no,))
            
            conn.commit()
            
            return {
                "accession_number": acc_no,
                "ticker": ticker,
                "market": market,
                "retry_count": retry_count
            }

    def complete_job(self, accession_number: str):
        """ジョブの完了を記録する"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE jobs 
                SET status = 'COMPLETED', updated_at = CURRENT_TIMESTAMP, error_message = NULL
                WHERE accession_number = ?
            ''', (accession_number,))
            conn.commit()

    def fail_job(self, accession_number: str, error_message: str):
        """ジョブの失敗を記録し、リトライ回数を増やす"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE jobs 
                SET status = 'FAILED', 
                    retry_count = retry_count + 1, 
                    error_message = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE accession_number = ?
            ''', (str(error_message), accession_number))
            conn.commit()
            
    def get_stats(self) -> Dict[str, int]:
        """キューの状態を取得する"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT status, COUNT(*) FROM jobs GROUP BY status')
            rows = cursor.fetchall()
            stats = {row[0]: row[1] for row in rows}
            # 未定義のステータスは0埋め
            for state in ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']:
                if state not in stats:
                    stats[state] = 0
            return stats
