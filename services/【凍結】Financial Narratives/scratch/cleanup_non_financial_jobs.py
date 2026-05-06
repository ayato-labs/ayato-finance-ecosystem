import sqlite3
import duckdb
from loguru import logger

def cleanup():
    # 1. DuckDBから10-K, 10-Q以外のaccession_numberを取得
    # 米国市場のDB
    duck_conn = duckdb.connect("data/narratives_us.duckdb", read_only=True)
    rows = duck_conn.execute("SELECT accession_number FROM filings WHERE form NOT IN ('10-K', '10-Q')").fetchall()
    non_target_accs = [r[0] for r in rows]
    duck_conn.close()

    if not non_target_accs:
        logger.info("No non-target filings found in Data Lake.")
        return

    logger.warning(f"Found {len(non_target_accs)} non-target filings (Form 4, 8-K, etc.). Cleaning up jobs...")

    # 2. SQLiteから該当するジョブを削除
    sqlite_conn = sqlite3.connect("data/sync_master.sqlite")
    # 大量にあるため、一時テーブルまたはIN句で処理
    cursor = sqlite_conn.cursor()
    
    # 削除実行
    # プレースホルダの制限を避けるため、1000件ずつ処理
    batch_size = 500
    total_deleted = 0
    for i in range(0, len(non_target_accs), batch_size):
        batch = non_target_accs[i:i+batch_size]
        placeholders = ','.join(['?'] * len(batch))
        res = cursor.execute(f"DELETE FROM jobs WHERE accession_number IN ({placeholders})", batch)
        total_deleted += res.rowcount
    
    sqlite_conn.commit()
    sqlite_conn.close()
    
    logger.success(f"Cleanup finished. Deleted {total_deleted} noisy jobs from queue.")

if __name__ == "__main__":
    cleanup()
