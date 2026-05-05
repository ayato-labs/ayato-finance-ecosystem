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

    def _safe_connect(self, db_path: str, read_only: bool = True):
        """Windows環境でのファイルロック競合を回避しながらDuckDBに接続する"""
        import time
        import random
        for attempt in range(10):
            try:
                return duckdb.connect(db_path, read_only=read_only)
            except Exception as e:
                err_str = str(e).lower()
                if "cannot open file" in err_str or "already open" in err_str or "lock" in err_str:
                    wait_time = (2 ** attempt) * 0.1 + random.uniform(0, 0.5)
                    if attempt > 2:
                        logger.warning(f"DB {db_path} locked by another process, retrying in {wait_time:.2f}s...")
                    time.sleep(wait_time)
                    continue
                raise e
        raise RuntimeError(f"Failed to connect to DuckDB after multiple attempts: {db_path}")

    def _get_lake_accessions(self, storage: FinancialNarrativeStorage) -> dict[str, str]:
        """Lake (filings) に存在する {accession_number: ticker} の辞書を取得"""
        with self._safe_connect(storage.db_path, read_only=True) as conn:
            # 必要なカラムだけを取得
            rows = conn.execute("SELECT accession_number, ticker FROM filings").fetchall()
            return {row[0]: row[1] for row in rows}

    def _get_structured_accessions(self, storage: FinancialNarrativeStorage) -> set[str]:
        """既に構造化済みの accession_number のセットを取得"""
        with self._safe_connect(storage.db_path, read_only=True) as conn:
            rows = conn.execute("SELECT accession_number FROM structured_data").fetchall()
            return {row[0] for row in rows}

    def reconcile_market(self, market: str):
        """指定した市場の差分を計算し、キューに積む"""
        logger.info(f"Starting reconciliation for {market.upper()} market...")
        storage = self.storage_jp if market == "jp" else self.storage_us

        lake_data = self._get_lake_accessions(storage)
        structured_keys = self._get_structured_accessions(storage)

        # 1. 差分抽出 (Lakeにはあるが、Structuredには無いもの) -> キューに追加
        pending_accessions = set(lake_data.keys()) - structured_keys
        enqueued_count = 0
        for acc_no in pending_accessions:
            ticker = lake_data[acc_no]
            if self.queue.enqueue_job(acc_no, ticker, market):
                enqueued_count += 1

        # 2. 逆方向の同期 (Structuredにあるが SQLite で完了になっていないものを救済)
        # 以前の実行で DuckDB 書き込み成功 -> SQLite 更新前にクラッシュしたケースを修復
        synced_count = 0
        for acc_no in structured_keys:
            # すでに存在する場合は内部でステータスが更新される
            # (注: 大量にある場合はパフォーマンス向上のため改善の余地ありだが、現状は確実性を優先)
            self.queue.complete_job(acc_no)
            synced_count += 1

        logger.success(
            f"Reconciliation for {market.upper()} completed. "
            f"Lake: {len(lake_data)}, Structured: {len(structured_keys)}, "
            f"Newly Enqueued: {enqueued_count}, Synced Completed: {synced_count}"
        )

    def run(self, market: str | None = None):
        """指定された市場、または全市場の調停を実行する"""
        try:
            # 0. 起動時の強制クリーンアップ (アクティブなジョブをすべて PENDING に戻す)
            self.queue.force_reset_active_jobs()

            # 1. ゾンビジョブ (PROCESSING のまま停滞) のクリーンアップ
            self.queue.cleanup_zombie_jobs(timeout_minutes=60)

            # 2. 市場ごとの調停
            if not market or market == "jp":
                self.reconcile_market("jp")
            if not market or market == "us":
                self.reconcile_market("us")

            stats = self.queue.get_stats()
            logger.info(f"Current Job Queue Stats ({market or 'ALL'}): {stats}")
        except Exception as e:
            logger.exception(f"Critical error during reconciliation: {e}")


if __name__ == "__main__":
    from src.logging_utils import setup_logging
    setup_logging("reconciler")
    reconciler = Reconciler()
    reconciler.run()
