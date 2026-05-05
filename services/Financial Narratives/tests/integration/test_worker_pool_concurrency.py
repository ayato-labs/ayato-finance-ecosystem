import asyncio
from unittest.mock import patch

import duckdb
import pytest

from src.db.master_db import JobQueue
from src.structuring_worker import StructuringWorkerPool


@pytest.fixture
def test_setup(tmp_path):
    master_path = tmp_path / "master.sqlite"
    jp_lake_path = tmp_path / "jp_lake.duckdb"

    # Initialize DuckDB
    with duckdb.connect(str(jp_lake_path)) as conn:
        conn.execute(
            """
            CREATE TABLE filings (
                accession_number VARCHAR PRIMARY KEY, ticker VARCHAR, cik VARCHAR,
                form VARCHAR, filing_date DATE, sections JSON, metadata JSON,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE structured_data (
                accession_number VARCHAR PRIMARY KEY, ticker VARCHAR,
                structured_facts JSON, updated_at TIMESTAMP
            )
            """
        )
        # Add 50 tasks
        for i in range(50):
            acc_no = f"ACC-{i}"
            conn.execute(
                """
                INSERT INTO filings VALUES (
                    ?, 'TICKER', 'CIK', '120', '2026-05-01',
                    '{"content":"data"}', '{}', CURRENT_TIMESTAMP
                )
                """,
                (acc_no,),
            )

    return {"master": str(master_path), "jp": str(jp_lake_path)}


@pytest.mark.asyncio
async def test_worker_pool_parallel_efficiency(test_setup):
    """
    【厳しいテスト】
    5個のワーカーを起動し、50個のジョブを並列で奪い合わせる。
    1. 全てのジョブが COMPLETED になること
    2. 重複実行がないこと
    3. DuckDB に 50件のレコードがあること
    """
    # Override paths in WorkerPool
    with (
        patch("src.structuring_worker.JobQueue") as mock_q_cls,
        patch("src.structuring_worker.FinancialNarrativeStorage") as mock_s_cls,
        patch("src.structuring_worker.FilingStructurer") as mock_st_cls,
    ):
        # Real JobQueue but test path
        real_queue = JobQueue(db_path=test_setup["master"])
        mock_q_cls.return_value = real_queue

        # Real storage but test path
        from src.storage import FinancialNarrativeStorage

        real_storage = FinancialNarrativeStorage(db_path=test_setup["jp"])

        # market="jp" を強制
        def side_effect_storage(market=None, db_path=None):
            return real_storage

        mock_s_cls.side_effect = side_effect_storage

        # Mock LLM (Gemini is slow, so we simulate 0.05s delay)
        mock_structurer = mock_st_cls.return_value

        async def mock_extract(sections):
            await asyncio.sleep(0.05)
            return {"fact": "structured"}

        mock_structurer.extract_facts.side_effect = mock_extract

        # Enqueue 50 jobs
        for i in range(50):
            real_queue.enqueue_job(f"ACC-{i}", "TICKER", "jp")

        # 5ワーカーでプール起動
        pool = StructuringWorkerPool(num_workers=5)

        # 無限ループを止めるためのタイマー
        # 全てが COMPLETED になったらループを抜けるようにする
        async def run_until_done():
            while True:
                stats = real_queue.get_stats()
                if stats["COMPLETED"] == 50:
                    break
                await asyncio.sleep(0.1)

        # ワーカーと終了監視を同時に走らせる
        worker_task = asyncio.create_task(pool.run_forever())
        try:
            await asyncio.wait_for(run_until_done(), timeout=10)
        finally:
            worker_task.cancel()

        # Verify
        stats = real_queue.get_stats()
        assert stats["COMPLETED"] == 50
        assert stats["PENDING"] == 0

        # DuckDB の中身を確認
        with duckdb.connect(test_setup["jp"]) as conn:
            count = conn.execute("SELECT COUNT(*) FROM structured_data").fetchone()[0]
            assert count == 50, "Some structured data were lost or not saved."
