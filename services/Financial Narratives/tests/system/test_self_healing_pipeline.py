import pytest
import asyncio
import duckdb
import os
from unittest.mock import MagicMock, patch, AsyncMock
from src.batch_fetch import batch_fetch
from src.reconciler import Reconciler
from src.structuring_worker import StructuringWorkerPool

@pytest.fixture
def clean_env(tmp_path):
    dbs = {
        "jp": str(tmp_path / "jp.duckdb"),
        "us": str(tmp_path / "us.duckdb"),
        "master": str(tmp_path / "master.sqlite")
    }
    return dbs

@pytest.mark.asyncio
async def test_self_healing_user_flow(clean_env):
    """
    【総合テスト】
    1. Ingestion: データ取得 (Mocked API)
    2. Reconciliation: 差分検知
    3. Work: 構造化実行 (Mocked LLM)
    4. 自己修復: データを1件消して、もう一度フローを回して復活することを確認
    """
    
    # --- Mocks ---
    with patch("src.batch_fetch.EdgarFetcher") as mock_edgar_cls, \
         patch("src.batch_fetch.EdinetFetcher") as mock_edinet_cls, \
         patch("src.batch_fetch.FinancialNarrativeStorage") as mock_storage_cls, \
         patch("src.reconciler.FinancialNarrativeStorage") as mock_rec_storage_cls, \
         patch("src.reconciler.JobQueue") as mock_rec_q_cls, \
         patch("src.structuring_worker.JobQueue") as mock_worker_q_cls, \
         patch("src.structuring_worker.FinancialNarrativeStorage") as mock_worker_storage_cls, \
         patch("src.structuring_worker.FilingStructurer") as mock_st_cls:
        
        # Real objects using temp paths
        from src.storage import FinancialNarrativeStorage
        from src.db.master_db import JobQueue
        
        storage_jp = FinancialNarrativeStorage(db_path=clean_env["jp"])
        storage_us = FinancialNarrativeStorage(db_path=clean_env["us"])
        master_q = JobQueue(db_path=clean_env["master"])
        
        # 配線
        def mock_storage_side_effect(market=None, db_path=None):
            if market == "jp": return storage_jp
            return storage_us
            
        mock_storage_cls.side_effect = mock_storage_side_effect
        mock_rec_storage_cls.side_effect = mock_storage_side_effect
        mock_worker_storage_cls.side_effect = mock_storage_side_effect
        
        mock_rec_q_cls.return_value = master_q
        mock_worker_q_cls.return_value = master_q
        
        # API Mocks (US 1件だけ取得させる)
        mock_edgar = mock_edgar_cls.return_value
        mock_edgar.get_latest_submissions.return_value = {"filings": {"recent": {}}}
        mock_edgar.filter_relevant_filings.return_value = [
            {"accessionNumber": "HEAL-ME", "filingDate": "2026-05-01", "primaryDocument": "d.htm", "form": "10-Q"}
        ]
        mock_edgar.get_cik.return_value = "001"
        
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "<html>Content</html>"
            mock_get.return_value = mock_resp
            
            # 1. Ingestion
            await batch_fetch(tickers=["AAPL"], days=1)
            
        # 2. Reconcile
        reconciler = Reconciler()
        reconciler.run()
        assert master_q.get_stats()["PENDING"] == 1
        
        # 3. Work
        mock_st = mock_st_cls.return_value
        mock_st.extract_facts.return_value = {"status": "healthy"}
        
        pool = StructuringWorkerPool(num_workers=1)
        # 1件だけ回すためのヘルパー
        async def run_once():
            while master_q.get_stats()["COMPLETED"] < 1:
                await asyncio.sleep(0.1)
        
        worker_task = asyncio.create_task(pool.run_forever())
        await asyncio.wait_for(run_once(), timeout=5)
        worker_task.cancel()
        
        # 確認
        with duckdb.connect(clean_env["us"]) as conn:
            assert conn.execute("SELECT COUNT(*) FROM structured_data").fetchone()[0] == 1
            
        # 4. 【自己修復の試練】意図的にデータを消す
        with duckdb.connect(clean_env["us"]) as conn:
            conn.execute("DELETE FROM structured_data WHERE accession_number = 'HEAL-ME'")
            
        # 再び Reconcile -> Work
        reconciler.run()
        assert master_q.get_stats()["PENDING"] == 1 # 復活している
        
        worker_task = asyncio.create_task(pool.run_forever())
        await asyncio.wait_for(run_once(), timeout=5)
        worker_task.cancel()
        
        # 復活したか確認
        with duckdb.connect(clean_env["us"]) as conn:
            assert conn.execute("SELECT COUNT(*) FROM structured_data").fetchone()[0] == 1
            print("\nSelf-healing verified successfully.")
