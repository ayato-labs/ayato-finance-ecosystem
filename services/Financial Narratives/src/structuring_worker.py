import asyncio
import gc
import json
import os

import duckdb
from dotenv import load_dotenv
from loguru import logger

from src.config import GOOGLE_AI_MODELS
from src.db.master_db import JobQueue
from src.logging_utils import setup_logging
from src.storage import FinancialNarrativeStorage
from src.structurer import FilingStructurer

load_dotenv()

# DuckDBへの並行書き込みを安全に行うためのプロセス内ロック
db_write_lock_jp = asyncio.Lock()
db_write_lock_us = asyncio.Lock()


class StructuringWorkerPool:
    """
    マスターDBから未処理のタスクをアトミックに取得し、
    LLM推論を並行で実行して Structured DB に書き込むコンシューマー群。
    モデルごとにワーカーを分散させ、APIのレート制限を最大限に活用する。
    """

    def __init__(self, num_workers: int = 10):
        self.num_workers = num_workers
        self.queue = JobQueue()
        self.storage_jp = FinancialNarrativeStorage(market="jp")
        self.storage_us = FinancialNarrativeStorage(market="us")
        self.api_key = os.getenv("GOOGLE_API_KEY")

        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY must be set to run structuring workers.")

    async def _get_sections_from_lake(self, accession_number: str, market: str) -> dict:
        """Data Lake (DuckDB) から生のテキストセクションを取得する"""
        storage = self.storage_jp if market == "jp" else self.storage_us

        def fetch_db():
            import time
            for attempt in range(5):
                try:
                    with duckdb.connect(storage.db_path, read_only=True) as conn:
                        res = conn.execute(
                            "SELECT sections FROM filings WHERE accession_number = ?",
                            (accession_number,)
                        ).fetchone()
                        if res and res[0]:
                            return json.loads(res[0])
                        return {}
                except Exception as e:
                    if "already open" in str(e) or "Unique file handle conflict" in str(e):
                        logger.warning(f"DB locked, retrying fetch ({attempt+1}/5)...")
                        time.sleep(1)
                        continue
                    raise e
            return {}

        return await asyncio.to_thread(fetch_db)

    async def _worker_loop(self, worker_id: int, model_name: str):
        """個々のワーカーの無限ループ"""
        logger.info(f"Worker-{worker_id} started using model: {model_name}")
        structurer = FilingStructurer(api_key=self.api_key, model_name=model_name)

        while True:
            try:
                # 1. アトミックにタスクを取得
                job = await asyncio.to_thread(self.queue.dequeue_job)

                if not job:
                    await asyncio.sleep(5)
                    continue

                acc_no = job["accession_number"]
                ticker = job["ticker"]
                market = job["market"]
                retry_count = job["retry_count"]

                logger.info(
                    f"[Worker-{worker_id}|{model_name}] Dequeued {acc_no} "
                    f"({ticker}, retry: {retry_count})"
                )

                # 2. Data Lake からテキストを取得
                sections = await self._get_sections_from_lake(acc_no, market)
                if not sections:
                    raise ValueError("No sections found in Data Lake")

                # 3. LLM 推論 (API呼び出し)
                facts = await structurer.extract_facts(sections)

                if not facts:
                    raise RuntimeError("LLM returned empty or failed to extract facts")

                # 4. Structured DB への書き込み
                storage = self.storage_jp if market == "jp" else self.storage_us
                db_lock = db_write_lock_jp if market == "jp" else db_write_lock_us

                async with db_lock:
                    def save_db():
                        import time
                        for attempt in range(10):
                            try:
                                storage.save_structuring(acc_no, ticker, facts)
                                return
                            except Exception as e:
                                if "already open" in str(e) or "Unique file handle conflict" in str(e):
                                    logger.warning(f"DB locked, retrying save ({attempt+1}/10)...")
                                    time.sleep(2)
                                    continue
                                raise e
                    await asyncio.to_thread(save_db)

                # 5. SQLite ステータスの完了更新
                await asyncio.to_thread(self.queue.complete_job, acc_no)
                logger.success(f"[Worker-{worker_id}|{model_name}] Completed {acc_no} ({ticker})")

                # メモリ解放の補助
                del sections
                del facts
                gc.collect()

            except Exception as e:
                if 'job' in locals() and job:
                    logger.error(f"[Worker-{worker_id}|{model_name}] Failed {acc_no}: {e}")
                    await asyncio.to_thread(self.queue.fail_job, acc_no, str(e))
                else:
                    logger.error(f"[Worker-{worker_id}] Unhandled error in loop: {e}")
                    await asyncio.sleep(2)

    async def run_forever(self):
        """指定された数のワーカーを起動し、永久に走らせる"""
        logger.info(
            f"Starting Worker Pool with {self.num_workers} workers "
            f"across {len(GOOGLE_AI_MODELS)} models..."
        )

        tasks = []
        for i in range(self.num_workers):
            # モデルを順番に割り当てて分散させる
            model_name = GOOGLE_AI_MODELS[i % len(GOOGLE_AI_MODELS)]
            tasks.append(asyncio.create_task(self._worker_loop(i, model_name)))

        await asyncio.gather(*tasks)


if __name__ == "__main__":
    setup_logging("worker_pool")

    import argparse
    parser = argparse.ArgumentParser(description="Start the Parallel Structuring Worker Pool")
    parser.add_argument("--workers", type=int, default=10, help="Number of concurrent LLM workers")
    args = parser.parse_args()

    pool = StructuringWorkerPool(num_workers=args.workers)

    try:
        asyncio.run(pool.run_forever())
    except KeyboardInterrupt:
        logger.info("Worker pool stopped by user.")
