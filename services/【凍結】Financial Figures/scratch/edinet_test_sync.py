from src.edinet.sync_worker import EDINETSyncWorker
from loguru import logger
import datetime

def edinet_init_and_test():
    worker = EDINETSyncWorker()
    
    # 1. マスターデータの初期化
    logger.info("Step 1: Synchronizing EDINET Ticker Master...")
    worker.ensure_ticker_master(force_update=True)
    
    # 2. 直近7日間の増分同期テスト
    logger.info("Step 2: Running test sync for the last 7 days...")
    # EDINET APIは週末も稼働していますが、有報提出は平日が多いため遡ります
    worker.run_backfill(days=7)
    
    logger.info("EDINET initialization and test complete.")

if __name__ == "__main__":
    edinet_init_and_test()
