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
            import random
            for attempt in range(10):
                try:
                    # read_only=True かつメモリ制限を明示して接続
                    with duckdb.connect(storage.db_path, read_only=True) as conn:
                        conn.execute("PRAGMA memory_limit='256MB'")
                        conn.execute("PRAGMA threads=1")  # ワーカー内では単一スレッドで十分
                        res = conn.execute(
                            "SELECT sections FROM filings WHERE accession_number = ?",
                            (accession_number,)
                        ).fetchone()
                        if res and res[0]:
                            sections_data = json.loads(res[0])
                            return sections_data
                        return {}
                except Exception as e:
                    err_str = str(e).lower()
                    if any(kw in err_str for kw in ["already open", "file handle conflict", "io error"]):
                        wait_time = (2 ** attempt) * 0.1 + random.uniform(0, 0.2)
                        logger.warning(
                            f"DB locked, retrying fetch in {wait_time:.2f}s ({attempt+1}/10)..."
                        )
                        time.sleep(wait_time)
                        continue
                    raise e
            return {}

        return await asyncio.to_thread(fetch_db)

    async def _worker_loop(self, worker_id: int, model_name: str):
        """個々のワーカーの無限ループ"""
        logger.info(f"Worker-{worker_id} started using model: {model_name}")
        structurer = FilingStructurer(api_key=self.api_key, model_name=model_name)

        while True:
            job = None
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
                    f"[Worker-{worker_id}] Processing {acc_no} ({ticker}, retry: {retry_count})"
                )

                # 2. Data Lake からテキストを取得 (FETCHING)
                try:
                    await asyncio.to_thread(
                        self.queue.update_job_status, acc_no, "FETCHING", f"{worker_id}|{model_name}"
                    )
                    sections = await self._get_sections_from_lake(acc_no, market)
                    if not sections:
                        raise ValueError("No sections found in Data Lake")
                    
                    section_count = len(sections)
                    logger.info(
                        f"[Worker-{worker_id}] Document Loaded: {section_count} sections for {acc_no}"
                    )
                except Exception as e:
                    logger.exception(f"[Worker-{worker_id}] FETCH_FAILED for {acc_no}: {e}")
                    await asyncio.to_thread(self.queue.fail_job, acc_no, f"FETCH_ERR: {str(e)}")
                    continue

                # 3. LLM 推論 (LLM_WAITING)
                try:
                    await asyncio.to_thread(
                        self.queue.update_job_status,
                        acc_no,
                        "LLM_WAITING",
                        f"{worker_id}|{model_name}"
                    )
                    logger.info(f"[Worker-{worker_id}] Requesting LLM extraction for {acc_no}...")
                    facts = await structurer.extract_facts(sections)

                    if not facts:
                        logger.error(f"[Worker-{worker_id}] LLM_EMPTY: No facts extracted for {acc_no}")
                        await asyncio.to_thread(self.queue.fail_job, acc_no, "LLM_EMPTY_RESPONSE")
                        continue
                    
                    if isinstance(facts, list):
                        fact_count = len(facts)
                    elif isinstance(facts, dict):
                        fact_count = len(facts.get("facts", []))
                    else:
                        fact_count = "N/A"

                    logger.success(
                        f"[Worker-{worker_id}] LLM Extraction Succeeded: "
                        f"{fact_count} items for {acc_no}"
                    )
                except Exception as e:
                    logger.error(f"[Worker-{worker_id}] LLM_FAILED for {acc_no}: {e}")
                    await asyncio.to_thread(self.queue.fail_job, acc_no, f"LLM_ERR: {str(e)}")
                    continue
                finally:
                    # テキストデータは巨大なため、推論が終わったら即座に解放を試みる
                    del sections
                    gc.collect()

                # 4. 解析結果を SQLite に一時保存 (Writerに委譲)
                try:
                    result_json = json.dumps(facts, ensure_ascii=False)
                    await asyncio.to_thread(self.queue.store_parsed_result, acc_no, result_json)
                    logger.info(f"[Worker-{worker_id}] Result Staged to SQLite: {acc_no}")
                except Exception as e:
                    logger.exception(f"[Worker-{worker_id}] STAGING_FAILED for {acc_no}: {e}")
                    await asyncio.to_thread(self.queue.fail_job, acc_no, f"STAGE_ERR: {str(e)}")
                    continue
                finally:
                    del facts
                    gc.collect()

            except Exception as e:
                logger.exception(f"[Worker-{worker_id}] UNEXPECTED_CRITICAL_ERROR: {e}")
                if job and 'acc_no' in locals():
                    await asyncio.to_thread(self.queue.fail_job, acc_no, f"CRITICAL: {str(e)}")
                await asyncio.sleep(5)

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
