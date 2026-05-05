import json
import time

from loguru import logger

from src.db.master_db import JobQueue
from src.logging_utils import setup_logging
from src.storage import FinancialNarrativeStorage


def run_writer():
    setup_logging(unit_name="writer")
    queue = JobQueue()
    storage_jp = FinancialNarrativeStorage(market="jp")
    storage_us = FinancialNarrativeStorage(market="us")

    logger.info("Starting Single Writer (DuckDB Serializer) process...")

    last_heartbeat = 0
    while True:
        try:
            # 1. PARSED ステータスのジョブを一括取得 (最大20件)
            parsed_jobs = queue.get_parsed_jobs(limit=20)

            if not parsed_jobs:
                current_time = time.time()
                if current_time - last_heartbeat > 30:
                    logger.info("Writer is active: Waiting for parsed jobs from LLM workers...")
                    last_heartbeat = current_time
                time.sleep(5)
                continue

            logger.info(f"Retrieved {len(parsed_jobs)} parsed jobs to serialize.")

            # 2. 市場ごとにデータを分類
            batch_jp = []
            batch_us = []
            job_acc_nos = []

            for job in parsed_jobs:
                acc_no = job["accession_number"]
                ticker = job["ticker"]
                market = job["market"]
                result_json = job["result_json"]

                try:
                    if not result_json:
                        logger.warning(f"Empty result_json for {acc_no}, skipping.")
                        continue

                    facts = json.loads(result_json)
                    if market == "jp":
                        batch_jp.append((acc_no, ticker, facts))
                    else:
                        batch_us.append((acc_no, ticker, facts))

                    job_acc_nos.append(acc_no)

                    # ステータスを一旦 SAVING に変更 (一括で行うと効率的)
                    queue.update_job_status(acc_no, "SAVING", "writer")
                except Exception as e:
                    logger.error(f"Error preparing batch for {acc_no}: {e}")
                    queue.fail_job(acc_no, f"PREPARE_ERR: {str(e)}")

            # 3. DuckDB に一括書き込み
            if batch_jp:
                storage_jp.save_structuring_batch(batch_jp)
            if batch_us:
                storage_us.save_structuring_batch(batch_us)

            # 4. 全ジョブを完了マーク
            for acc_no in job_acc_nos:
                queue.complete_job(acc_no)

            if job_acc_nos:
                logger.success(f"[Writer] Successfully bulk serialized {len(job_acc_nos)} jobs.")

        except Exception as e:
            logger.exception(f"[Writer] Critical error in writer loop: {e}")
            time.sleep(10)


if __name__ == "__main__":
    try:
        run_writer()
    except KeyboardInterrupt:
        logger.info("Writer stopped by user.")
    except Exception as e:
        logger.critical(f"Writer crashed: {e}", exc_info=True)
