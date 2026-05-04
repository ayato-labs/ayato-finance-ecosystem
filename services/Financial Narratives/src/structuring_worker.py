import asyncio
import os
import json
import duckdb
from loguru import logger
from dotenv import load_dotenv

from src.db.master_db import JobQueue
from src.storage import FinancialNarrativeStorage
from src.structurer import FilingStructurer
from src.logging_utils import setup_logging

load_dotenv()

# DuckDBへの並行書き込みを安全に行うためのプロセス内ロック
db_write_lock_jp = asyncio.Lock()
db_write_lock_us = asyncio.Lock()

class StructuringWorkerPool:
    """
    マスターDBから未処理のタスクをアトミックに取得し、
    LLM推論を並行で実行して Structured DB に書き込むコンシューマー群。
    """
    
    def __init__(self, num_workers: int = 10):
        self.num_workers = num_workers
        self.queue = JobQueue()
        self.storage_jp = FinancialNarrativeStorage(market="jp")
        self.storage_us = FinancialNarrativeStorage(market="us")
        
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY must be set to run structuring workers.")
        self.structurer = FilingStructurer(api_key=api_key)

    async def _get_sections_from_lake(self, accession_number: str, market: str) -> dict:
        """Data Lake (DuckDB) から生のテキストセクションを取得する"""
        storage = self.storage_jp if market == "jp" else self.storage_us
        
        # CPUバウンドまたはI/Oバウンドなので to_thread に逃がす
        def fetch_db():
            with duckdb.connect(storage.db_path) as conn:
                res = conn.execute(
                    "SELECT sections FROM filings WHERE accession_number = ?", 
                    (accession_number,)
                ).fetchone()
                if res and res[0]:
                    return json.loads(res[0])
                return {}
                
        return await asyncio.to_thread(fetch_db)

    async def _worker_loop(self, worker_id: int):
        """個々のワーカーの無限ループ"""
        logger.info(f"Worker-{worker_id} started.")
        while True:
            try:
                # 1. アトミックにタスクを取得 (他のワーカーと競合しない)
                # SQLite I/O
                job = await asyncio.to_thread(self.queue.dequeue_job)
                
                if not job:
                    # キューが空の場合は少し待機
                    await asyncio.sleep(5)
                    continue
                    
                acc_no = job["accession_number"]
                ticker = job["ticker"]
                market = job["market"]
                retry_count = job["retry_count"]
                
                logger.info(f"[Worker-{worker_id}] Dequeued {acc_no} ({ticker}, retry: {retry_count})")
                
                # 2. Data Lake からテキストを取得
                sections = await self._get_sections_from_lake(acc_no, market)
                if not sections:
                    raise ValueError("No sections found in Data Lake")

                # 3. LLM 推論 (API呼び出し)
                # Geminiへのリクエストは内部で非同期化されている
                facts = await self.structurer.extract_facts(sections)
                
                if not facts:
                    # LLMが意図的に空を返したか、内部エラーをキャッチした場合
                    raise RuntimeError("LLM returned empty or failed to extract facts")

                # 4. Structured DB への書き込み
                storage = self.storage_jp if market == "jp" else self.storage_us
                db_lock = db_write_lock_jp if market == "jp" else db_write_lock_us
                
                async with db_lock:
                    await asyncio.to_thread(storage.save_structuring, acc_no, ticker, facts)
                
                # 5. SQLite ステータスの完了更新
                await asyncio.to_thread(self.queue.complete_job, acc_no)
                logger.success(f"[Worker-{worker_id}] Completed {acc_no} ({ticker})")
                
            except Exception as e:
                # 失敗時はステータスを FAILED に変更し、リトライ回数を増やす
                if 'job' in locals() and job:
                    logger.error(f"[Worker-{worker_id}] Failed {job['accession_number']}: {e}")
                    await asyncio.to_thread(self.queue.fail_job, job['accession_number'], str(e))
                else:
                    logger.error(f"[Worker-{worker_id}] Unhandled error in loop: {e}")
                    await asyncio.sleep(2)

    async def run_forever(self):
        """指定された数のワーカーを起動し、永久に走らせる"""
        logger.info(f"Starting Worker Pool with {self.num_workers} parallel workers...")
        tasks = [asyncio.create_task(self._worker_loop(i)) for i in range(self.num_workers)]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    setup_logging("worker_pool")
    
    # コマンドライン引数で並列数を指定できるようにする
    import argparse
    parser = argparse.ArgumentParser(description="Start the Parallel Structuring Worker Pool")
    parser.add_argument("--workers", type=int, default=10, help="Number of concurrent LLM workers")
    args = parser.parse_args()
    
    pool = StructuringWorkerPool(num_workers=args.workers)
    
    try:
        asyncio.run(pool.run_forever())
    except KeyboardInterrupt:
        logger.info("Worker pool stopped by user.")