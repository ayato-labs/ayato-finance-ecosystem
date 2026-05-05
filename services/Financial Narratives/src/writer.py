import time
import json
from loguru import logger
from src.db.master_db import JobQueue
from src.storage import FinancialNarrativeStorage
from src.logging_utils import setup_logging

def run_writer():
    setup_logging(unit="writer")
    queue = JobQueue()
    storage_jp = FinancialNarrativeStorage(market="jp")
    storage_us = FinancialNarrativeStorage(market="us")
    
    logger.info("Starting Single Writer process...")
    
    while True:
        try:
            # 1. PARSED ステータスのジョブを取得
            parsed_jobs = queue.get_parsed_jobs(limit=10)
            
            if not parsed_jobs:
                time.sleep(5)
                continue
            
            for job in parsed_jobs:
                acc_no = job["accession_number"]
                ticker = job["ticker"]
                market = job["market"]
                result_json = job["result_json"]
                
                try:
                    facts = json.loads(result_json)
                    storage = storage_jp if market == "jp" else storage_us
                    
                    # 2. DuckDB に書き込み (直列なので競合しない)
                    storage.save_structuring(acc_no, ticker, facts)
                    
                    # 3. 完了マーク
                    queue.complete_job(acc_no)
                    logger.success(f"Successfully wrote {acc_no} ({ticker}) to DuckDB")
                    
                except Exception as e:
                    logger.error(f"Failed to write job {acc_no}: {e}")
                    queue.fail_job(acc_no, f"Writer Error: {str(e)}")
                    
        except Exception as e:
            logger.critical(f"Writer process encountered an error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run_writer()
