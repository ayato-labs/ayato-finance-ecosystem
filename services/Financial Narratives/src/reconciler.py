import duckdb
from loguru import logger
from src.db.master_db import JobQueue
from src.storage import FinancialNarrativeStorage

class Reconciler:
    """
    Data Lake と Structured DB の差分を監視し、
    未処理のタスクを Master DB のジョブキューに登録する。
    """
    
    def __init__(self):
        self.queue = JobQueue()
        self.storage_jp = FinancialNarrativeStorage(market="jp")
        self.storage_us = FinancialNarrativeStorage(market="us")

    def _get_lake_accessions(self, storage: FinancialNarrativeStorage) -> dict[str, str]:
        """Lake (filings) に存在する {accession_number: ticker} の辞書を取得"""
        with duckdb.connect(storage.db_path) as conn:
            # 必要なカラムだけを取得
            rows = conn.execute("SELECT accession_number, ticker FROM filings").fetchall()
            return {row[0]: row[1] for row in rows}

    def _get_structured_accessions(self, storage: FinancialNarrativeStorage) -> set[str]:
        """既に構造化済みの accession_number のセットを取得"""
        with duckdb.connect(storage.db_path) as conn:
            rows = conn.execute("SELECT accession_number FROM structured_data").fetchall()
            return {row[0] for row in rows}

    def reconcile_market(self, market: str):
        """指定した市場の差分を計算し、キューに積む"""
        logger.info(f"Starting reconciliation for {market.upper()} market...")
        storage = self.storage_jp if market == "jp" else self.storage_us
        
        lake_data = self._get_lake_accessions(storage)
        structured_keys = self._get_structured_accessions(storage)
        
        # 差分抽出 (Lakeにはあるが、Structuredには無いもの)
        pending_accessions = set(lake_data.keys()) - structured_keys
        
        enqueued_count = 0
        for acc_no in pending_accessions:
            ticker = lake_data[acc_no]
            if self.queue.enqueue_job(acc_no, ticker, market):
                enqueued_count += 1
                
        logger.success(
            f"Reconciliation for {market.upper()} completed. "
            f"Lake: {len(lake_data)}, Structured: {len(structured_keys)}, "
            f"Newly Enqueued: {enqueued_count}"
        )

    def run(self):
        """日米両市場の調停を実行する"""
        try:
            self.reconcile_market("jp")
            self.reconcile_market("us")
            
            stats = self.queue.get_stats()
            logger.info(f"Current Job Queue Stats: {stats}")
        except Exception as e:
            logger.exception(f"Critical error during reconciliation: {e}")

if __name__ == "__main__":
    from src.logging_utils import setup_logging
    setup_logging("reconciler")
    reconciler = Reconciler()
    reconciler.run()
