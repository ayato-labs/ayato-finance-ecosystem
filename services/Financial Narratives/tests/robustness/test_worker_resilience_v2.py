import pytest
import asyncio
import duckdb
from unittest.mock import MagicMock, patch, AsyncMock
from src.structuring_worker import StructuringWorkerPool
from src.db.master_db import JobQueue

@pytest.fixture
def robustness_env(tmp_path):
    return {
        "master": str(tmp_path / "master.sqlite"),
        "jp": str(tmp_path / "jp_lake.duckdb")
    }

@pytest.mark.asyncio
async def test_worker_poison_pill_isolation(robustness_env):
    """
    【堅牢性テスト】
    特定のタスクが「毒入り（致命的な例外を投げる）」であっても、
    他の正常なタスクが巻き添えにならず、システムが止まらないことを証明する。
    """
    with patch("src.structuring_worker.JobQueue") as mock_q_cls, \
         patch("src.structuring_worker.FinancialNarrativeStorage") as mock_s_cls, \
         patch("src.structuring_worker.FilingStructurer") as mock_st_cls:
        
        # Setup real JobQueue and storage with temp paths
        real_queue = JobQueue(db_path=robustness_env["master"])
        mock_q_cls.return_value = real_queue
        
        from src.storage import FinancialNarrativeStorage
        real_storage = FinancialNarrativeStorage(db_path=robustness_env["jp"])
        mock_s_cls.return_value = real_storage
        
        # Mock LLM: "POISON" というティッカーの時だけ例外を投げる
        mock_st = mock_st_cls.return_value
        async def mock_extract(sections):
            # 呼び出し元で ticker を判別するためのトリッキーな方法（実際は acc_no 等で判別）
            # ここでは単純に順序や内容で制御
            if "POISON" in str(sections):
                raise RuntimeError("CRITICAL API FAILURE: Poison Pill Triggered!")
            return {"fact": "safe"}
            
        mock_st.extract_facts.side_effect = mock_extract

        # DuckDBにデータを仕込む
        with duckdb.connect(robustness_env["jp"]) as conn:
            conn.execute("CREATE TABLE filings (accession_number VARCHAR PRIMARY KEY, ticker VARCHAR, cik VARCHAR, form VARCHAR, filing_date DATE, sections JSON, metadata JSON, updated_at TIMESTAMP)")
            conn.execute("CREATE TABLE structured_data (accession_number VARCHAR PRIMARY KEY, ticker VARCHAR, structured_facts JSON, updated_at TIMESTAMP)")
            conn.execute("INSERT INTO filings VALUES ('SAFE-1', 'GOOD', '0', '120', '2026-05-01', '{\"t\":\"safe\"}', '{}', CURRENT_TIMESTAMP)")
            conn.execute("INSERT INTO filings VALUES ('POISON-1', 'BAD', '0', '120', '2026-05-01', '{\"t\":\"POISON\"}', '{}', CURRENT_TIMESTAMP)")
            conn.execute("INSERT INTO filings VALUES ('SAFE-2', 'GOOD', '0', '120', '2026-05-01', '{\"t\":\"safe\"}', '{}', CURRENT_TIMESTAMP)")

        # ジョブ登録
        real_queue.enqueue_job("SAFE-1", "GOOD", "jp")
        real_queue.enqueue_job("POISON-1", "BAD", "jp")
        real_queue.enqueue_job("SAFE-2", "GOOD", "jp")

        pool = StructuringWorkerPool(num_workers=2)
        
        # 監視ループ
        async def wait_for_resolution():
            while True:
                stats = real_queue.get_stats()
                # 3件すべてが COMPLETED か FAILED になったら終了
                if stats["COMPLETED"] + stats["FAILED"] == 3:
                    break
                await asyncio.sleep(0.1)

        worker_task = asyncio.create_task(pool.run_forever())
        await asyncio.wait_for(wait_for_resolution(), timeout=5)
        worker_task.cancel()
        
        # 結果の検証
        stats = real_queue.get_stats()
        assert stats["COMPLETED"] == 2, "Normal jobs should have finished."
        assert stats["FAILED"] == 1, "Poison job should be marked as FAILED."
        
        # DuckDB のレコード数
        with duckdb.connect(robustness_env["jp"]) as conn:
            count = conn.execute("SELECT COUNT(*) FROM structured_data").fetchone()[0]
            assert count == 2, "Only successful extractions should be in DuckDB."
            
        print("\nRobustness (Poison Pill Isolation) verified.")
