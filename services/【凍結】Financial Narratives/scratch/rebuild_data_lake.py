import sqlite3
import json
from src.storage import FinancialNarrativeStorage
from src.edgar_parser import EdgarParser
from src.db.master_db import JobQueue
from loguru import logger

def rebuild():
    # 2. ジョブキューの差し戻し
    with sqlite3.connect("data/sync_master.sqlite") as conn:
        # result_jsonが '{}' または中身が空のCOMPLETEDジョブを特定
        # また、全件一括やり直しをしたい場合は 'us' 市場すべてを対象にする
        cursor = conn.execute("""
            SELECT accession_number, ticker 
            FROM jobs 
            WHERE market = 'us' AND (status = 'COMPLETED' OR status = 'FAILED')
        """)
        to_reset = cursor.fetchall()
        
        if to_reset:
            logger.warning(f"Found {len(to_reset)} US jobs. Resetting to PENDING for re-parsing...")
            for acc_no, ticker in to_reset:
                conn.execute(
                    "UPDATE jobs SET status = 'PENDING', result_json = NULL, error_message = NULL WHERE accession_number = ?",
                    (acc_no,)
                )
            conn.commit()
            logger.success(f"Reset {len(to_reset)} jobs to PENDING.")
        else:
            logger.info("No US jobs found to reset.")

if __name__ == "__main__":
    rebuild()
