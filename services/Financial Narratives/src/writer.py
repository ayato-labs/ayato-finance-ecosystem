import time
import json
from loguru import logger
from src.db.master_db import JobQueue
from src.storage import FinancialNarrativeStorage
from src.logging_utils import setup_logging

def run_writer():
    setup_logging(unit_name="writer")
    queue = JobQueue()
    storage_jp = FinancialNarrativeStorage(market="jp")
    storage_us = FinancialNarrativeStorage(market="us")
    
    logger.info("Starting Single Writer (DuckDB Serializer) process...")
    
    while True:
        try:
            # 1. PARSED ステータスのジョブを取得
            parsed_jobs = queue.get_parsed_jobs(limit=10)
            
            if not parsed_jobs:
                # 定期的に生存確認ログ
                # logger.debug("Waiting for parsed jobs...")
                time.sleep(5)
                continue
            
            logger.info(f"Retrieved {len(parsed_jobs)} parsed jobs to serialize.")
            
            for job in parsed_jobs:
                acc_no = job["accession_number"]
                ticker = job["ticker"]
                market = job["market"]
                result_json = job["result_json"]
                
                try:
                    # 2. DuckDB への書き込みフェーズ (SAVING)
                    queue.update_job_status(acc_no, "SAVING", "writer")
                    
                    if not result_json:
                        raise ValueError(f"Empty result_json for {acc_no}")
                        
                    facts = json.loads(result_json)
                    storage = storage_jp if market == "jp" else storage_us
                    
                    # 3. DuckDB に書き込み (直列なので競合しない)
                    storage.save_structuring(acc_no, ticker, facts)
                    
                    # 4. 完了マーク
                    queue.complete_job(acc_no)
                    logger.success(f"[Writer] Successfully serialized {acc_no} ({ticker}) to {market.upper()} DuckDB")
                    
                except Exception as e:
                    logger.exception(f"[Writer] Failed to serialize job {acc_no}: {e}")
                    queue.fail_job(acc_no, f"SERIALIZE_ERR: {str(e)}")
                    
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
