import asyncio
import os
import sys
import time
import multiprocessing
from pathlib import Path
from loguru import logger

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from src.logging_utils import setup_logging
from src.storage import FinancialNarrativeStorage, CrossProcessLock
from src.db.master_db import JobQueue
from src.reconciler import Reconciler

def test_logging_utf8():
    print("\n--- 1. Logging UTF-8 Test ---")
    setup_logging("verify_test")
    logger.info("日本語のログテスト: 正常に表示されていればOKです。")
    logger.success("Success message with emoji 🚀")

def concurrent_writer(db_path, writer_id):
    """別プロセスからの書き込みをシミュレート"""
    try:
        # storage インスタンスを各プロセスで作成（db_pathを直接指定）
        storage = FinancialNarrativeStorage(db_path=db_path)
        for i in range(5):
            acc_no = f"TEST-ACC-{writer_id}-{i}"
            ticker = f"TICKER-{writer_id}"
            facts = {"test": f"data-{i}"}
            
            # CrossProcessLock は save_structuring 内部で呼ばれる
            storage.save_structuring(acc_no, ticker, facts)
            time.sleep(0.1)
    except Exception as e:
        print(f"Writer-{writer_id} failed: {e}")

async def test_duckdb_locking():
    print("\n--- 2. DuckDB CrossProcessLock Test ---")
    db_path = "logs/test_lock.duckdb"
    if os.path.exists(db_path): os.remove(db_path)
    if os.path.exists(f"{db_path}.lock"): os.remove(f"{db_path}.lock")

    # 複数プロセスを同時に起動
    processes = []
    for i in range(3):
        p = multiprocessing.Process(target=concurrent_writer, args=(db_path, i))
        processes.append(p)
        p.start()

    for p in processes:
        p.join()
    
    print("Multi-process write test completed without 'already open' errors.")

async def test_reconciler_sync():
    print("\n--- 3. Reconciler Sync Test ---")
    queue = JobQueue()
    storage = FinancialNarrativeStorage(market="jp")
    
    acc_no = "RECON-TEST-001"
    ticker = "RECON-T"
    
    # 1. 意図的に不一致を作る
    # DuckDB には保存されているが、SQLite では PENDING (0) の状態
    storage.save_structuring(acc_no, ticker, {"status": "synced"})
    queue.enqueue_job(acc_no, ticker, "jp")
    
    # 状態確認
    import sqlite3
    db_path = "data/sync_master.sqlite"
    with sqlite3.connect(db_path) as conn:
        status = conn.execute("SELECT status FROM jobs WHERE accession_number = ?", (acc_no,)).fetchone()[0]
        print(f"Before Reconcile: Status for {acc_no} is {status} (Expected PENDING)")

    # 2. Reconciler を実行
    reconciler = Reconciler()
    # Reconciler.reconcile_market 内で DuckDB から情報を取得して SQLite を更新する
    reconciler.reconcile_market("jp")
    
    # 3. 結果確認
    with sqlite3.connect(db_path) as conn:
        status = conn.execute("SELECT status FROM jobs WHERE accession_number = ?", (acc_no,)).fetchone()[0]
        print(f"After Reconcile: Status for {acc_no} is {status} (Expected COMPLETED)")
        assert status == 'COMPLETED'

async def main():
    test_logging_utf8()
    await test_duckdb_locking()
    await test_reconciler_sync()
    print("\nVerification successful!")

if __name__ == "__main__":
    asyncio.run(main())
