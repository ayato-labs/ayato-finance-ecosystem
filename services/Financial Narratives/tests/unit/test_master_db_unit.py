import pytest
import sqlite3
import os
import concurrent.futures
from src.db.master_db import JobQueue

@pytest.fixture
def temp_master_db(tmp_path):
    db_file = tmp_path / "test_master.sqlite"
    return str(db_file)

def test_job_queue_basic_operations(temp_master_db):
    queue = JobQueue(db_path=temp_master_db)
    
    # Enqueue
    queue.enqueue_job("ACC-001", "T001", "jp")
    stats = queue.get_stats()
    assert stats["PENDING"] == 1
    
    # Dequeue
    job = queue.dequeue_job()
    assert job["accession_number"] == "ACC-001"
    assert queue.get_stats()["PROCESSING"] == 1
    
    # Complete
    queue.complete_job("ACC-001")
    assert queue.get_stats()["COMPLETED"] == 1
    assert queue.get_stats()["PROCESSING"] == 0

def test_job_queue_atomic_dequeue_concurrency(temp_master_db):
    """
    【厳しいテスト】
    複数のスレッドが同時に1つのジョブを奪い合った時、
    絶対に1つのスレッドしか取得できない（重複実行されない）ことを証明する。
    """
    queue = JobQueue(db_path=temp_master_db)
    queue.enqueue_job("UNIQUE-JOB", "TICKER", "us")
    
    results = []
    
    def try_dequeue(_):
        # 複数のスレッドで同時に実行
        return queue.dequeue_job()

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        # 20個のスレッドで一斉に1つのジョブを取りに行く
        futures = [executor.submit(try_dequeue, i) for i in range(20)]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res:
                results.append(res)
                
    # 20回試行しても、取得できたのは「たった1人」であること
    assert len(results) == 1, f"Double execution detected! {len(results)} threads got the same job."
    assert results[0]["accession_number"] == "UNIQUE-JOB"

def test_job_queue_retry_logic(temp_master_db):
    queue = JobQueue(db_path=temp_master_db)
    queue.enqueue_job("RETRY-ME", "T-RET", "jp")
    
    # 1. 失敗させる
    job = queue.dequeue_job()
    queue.fail_job(job["accession_number"], "Timeout")
    assert queue.get_stats()["FAILED"] == 1
    
    # 2. リトライされるか（もう一度 dequeue できるか）
    job_retry = queue.dequeue_job()
    assert job_retry is not None
    assert job_retry["retry_count"] == 1
    
    # 3. 3回失敗したら dequeue できなくなるか
    queue.fail_job(job_retry["accession_number"], "Error 2") # count=2
    queue.dequeue_job() # get
    queue.fail_job("RETRY-ME", "Error 3") # count=3
    
    last_try = queue.dequeue_job()
    assert last_try is None, "Job should not be dequeued after max retries."
