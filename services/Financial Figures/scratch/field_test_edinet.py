import logging
import os
from datetime import date, timedelta

from src.edinet.sync_worker import EDINETSyncWorker

# ログ出力を詳細化してトレーサビリティを確認
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("EDINET_FIELD_TEST")


def run_field_test():
    logger.info("Starting practical field test for EDINET module...")

    # APIキーの存在確認
    api_key = os.getenv("EDINET_API_KEY")
    if not api_key:
        logger.warning(
            "EDINET_API_KEY is not set in environment. This test is expected to fail at the network layer."
        )
    else:
        logger.info("EDINET_API_KEY found. Attempting real API connection.")

    try:
        worker = EDINETSyncWorker()

        # ターゲットを5日前に変更(2026-04-17 金曜日)
        target_date = date.today() - timedelta(days=5)
        logger.info(f"Targeting date: {target_date}")

        # 取得試行 (APIキーがない場合はここでエラーが出るはず)
        worker.sync_date(target_date)

        logger.info("Field test completed successfully.")

    except Exception as e:
        logger.error(f"Field test FAILED: {e}")


if __name__ == "__main__":
    run_field_test()
