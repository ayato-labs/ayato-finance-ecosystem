import sqlite3

import pytest

from src.db.master_db import JobQueue
from src.storage import FinancialNarrativeStorage


@pytest.mark.asyncio
async def test_job_lifecycle_integration(test_data_dir):
    db_file = str(test_data_dir / "test_integ.duckdb")
    q_file = str(test_data_dir / "test_integ.sqlite")
    storage = FinancialNarrativeStorage(db_path=db_file)
    queue = JobQueue(db_path=q_file)

    # 1. 保存と登録
    meta = {
        "accessionNumber": "INT-001",
        "ticker": "9999",
        "form": "有価証券報告書",
        "filingDate": "2024-05-01",
    }
    storage.save_filing(meta, {"section1": "text"})
    queue.enqueue_job(meta["accessionNumber"], meta["ticker"], "jp")

    # 2. キューからの取得
    job = queue.dequeue_job()
    assert job is not None
    assert job["accession_number"] == "INT-001"

    # SQLiteを直接確認
    with sqlite3.connect(queue.db_path) as conn:
        row = conn.execute("SELECT status FROM jobs WHERE accession_number = 'INT-001'").fetchone()
        assert row[0] == "PROCESSING"

    # 3. 失敗時のリバウンド
    queue.fail_job("INT-001", "Simulated Error")
    job_re = queue.dequeue_job()
    assert job_re is not None
    assert job_re["accession_number"] == "INT-001"
    assert job_re["retry_count"] == 1
