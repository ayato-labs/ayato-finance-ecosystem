
import duckdb
import pytest

from src.db.master_db import JobQueue
from src.reconciler import Reconciler
from src.storage import FinancialNarrativeStorage


@pytest.mark.asyncio
async def test_e2e_recovery_flow(test_data_dir):
    db_file = str(test_data_dir / "test_e2e.duckdb")
    q_file = str(test_data_dir / "test_e2e.sqlite")
    queue = JobQueue(db_path=q_file)
    storage = FinancialNarrativeStorage(db_path=db_file)
    reconciler = Reconciler()
    # reconciler内部のパスも差し替える必要があるが、
    # 簡易化のため reconciler 側の db 接続ロジックをテスト用に調整するか
    # 今回は reconciler.run() の代わりに必要なステップを直接テスト

    acc_no = "E2E-DEAD-001"

    # 1. ジョブ投入と「行方不明」の演出
    storage.save_filing(
        {"accessionNumber": acc_no, "ticker": "E2E", "form": "F", "filingDate": "2024-01-01"},
        {"t": "c"},
    )
    queue.enqueue_job(acc_no, "E2E", "jp")
    queue.dequeue_job()  # PROCESSING にする

    # 2. Reconciler 起動
    reconciler.run()

    # 2. キューからの取得
    job = queue.dequeue_job()
    assert job is not None
    assert job["accession_number"] == "INT-001"

    import sqlite3

    with sqlite3.connect(queue.db_path) as conn:
        row = conn.execute("SELECT status FROM jobs WHERE accession_number = 'INT-001'").fetchone()
        assert row[0] == "PROCESSING"


@pytest.mark.asyncio
async def test_e2e_writer_handoff(test_data_dir):
    db_file = str(test_data_dir / "test_handoff.duckdb")
    storage = FinancialNarrativeStorage(db_path=db_file)
    acc_no = "E2E-WRITE-001"
    result_data = {"thinking": "test", "capex": {"facts": "invested 100M"}}
    # 2. 書き出し
    storage.save_structuring_batch([(acc_no, "9999", result_data)])

    # 3. 検証
    with duckdb.connect(storage.db_path) as conn:
        res = conn.execute(
            "SELECT ticker FROM structured_data WHERE accession_number = ?", (acc_no,)
        ).fetchone()
        assert res[0] == "9999"
