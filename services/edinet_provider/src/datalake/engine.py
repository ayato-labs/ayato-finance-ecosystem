import datetime
import logging

from loguru import logger

from src.datalake.service.ingestor import DataIngestor
from src.datalake.shared.infra.db import db_manager
from src.datalake.shared.infra.migrations import MigrationManager
from src.datalake.shared.queries.repository import DataRepository

# Suppress edinet_tools LLM warning before it gets imported
logging.getLogger().setLevel(logging.ERROR)


class JPEDINETEngine:
    """
    Japanese Market Data Engine using EDINET API v2.
    Orchestrates discovery, ingestion, and repository access.
    """

    def __init__(self):
        logger.info("Initializing database and checking migrations...")
        MigrationManager.apply_migrations()
        self.ingestor = DataIngestor()
        self.repository = DataRepository()

    def sync_market(
        self,
        days: int | None = None,
        end_date: datetime.date | None = None,
        session_id: str = "market-sync",
        max_workers: int = 1,
        run_vacuum: bool = True,
    ):
        """
        Synchronizes market data from EDINET.
        - If 'days' is None, detects the last synced date from DB and bridges the gap.
        - Checks local registry to avoid redundant downloads.
        """
        if end_date is None:
            end_date = datetime.date.today()

        if days is not None:
            start_date = end_date - datetime.timedelta(days=days - 1)
        else:
            # Smart discovery: detect last filing date
            logger.info("Auto-detecting last sync date for smart discovery...")
            with db_manager.connect_master(read_only=True) as conn:
                res = conn.execute("SELECT MAX(submit_datetime) FROM registry_db.filings").fetchone()
                if res and res[0]:
                    # Start from the day after the last known filing
                    last_date = pd.to_datetime(res[0]).date()
                    start_date = last_date - datetime.timedelta(days=1)  # Buffer of 1 day to be safe
                    logger.info(f"Last filing found: {last_date}. Starting from {start_date}")
                else:
                    # Default for empty DB
                    start_date = end_date - datetime.timedelta(days=30)
                    logger.info(f"No existing filings. Starting with default {start_date}")

        logger.info(f"🚀 Launching Syncing market from {start_date} to {end_date}...")

        all_docs = []
        curr = start_date
        while curr <= end_date:
            try:
                docs = self.repository.get_documents_with_cache(curr)
                if docs:
                    all_docs.extend(docs)
            except Exception as e:
                logger.error(f"Failed to fetch documents for {curr}: {e}")
            curr += datetime.timedelta(days=1)

        if not all_docs:
            logger.warning(f"No documents discovered in the range {start_date} to {end_date}.")
            return

        logger.info(f"Discovery phase complete. Total candidates: {len(all_docs)}")

        # Process discovery results
        self.ingestor.process_docs_concurrently(all_docs, session_id, max_workers)

        if run_vacuum:
            self._vacuum_db()

        logger.info("✅ Market synchronization complete.")

    def sync_company(
        self,
        ticker: str,
        days: int = 30,
        session_id: str = "company-sync",
        max_workers: int = 1,
    ):
        """
        特定の銘柄（証券コード）に関連する書類のみを同期する。
        """
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=days - 1)
        logger.info(f"🔍 Syncing ticker {ticker} from {start_date} to {end_date}...")

        all_docs = []
        curr = start_date
        # 証券コードは通常4桁または5桁（末尾に0がある場合など）
        # EDINET APIの secCode は5桁で格納されていることが多い（例: 72030）
        ticker_clean = str(ticker).strip()

        while curr <= end_date:
            try:
                docs = self.repository.get_documents_with_cache(curr)
                if docs:
                    # 証券コードが前方一致するかチェック
                    filtered = [
                        d for d in docs 
                        if d._data.get("secCode") and str(d._data.get("secCode")).startswith(ticker_clean)
                    ]
                    all_docs.extend(filtered)
            except Exception as e:
                logger.error(f"Failed to fetch documents for {curr}: {e}")
            curr += datetime.timedelta(days=1)

        if not all_docs:
            logger.warning(f"No documents found for ticker {ticker} in the last {days} days.")
            return

        logger.info(f"Found {len(all_docs)} candidate documents for {ticker}.")
        self.ingestor.process_docs_concurrently(all_docs, session_id, max_workers)

    def _vacuum_db(self):
        """Maintenance: Reclaim space and optimize indexes."""
        logger.info("Running database maintenance (VACUUM)...")
        try:
            db_manager.checkpoint()
            with db_manager.connect_master() as conn:
                conn.execute("VACUUM")
                conn.execute("ANALYZE")
            logger.info("✅ Database maintenance complete.")
        except Exception as e:
            logger.warning(f"Maintenance failed (possible lock contention): {e}")

    def backfill_missing(self, max_workers: int = 1):
        """Public entry point for identifying gaps and filling them."""
        self.ingestor.backfill_missing_data(max_workers=max_workers)
