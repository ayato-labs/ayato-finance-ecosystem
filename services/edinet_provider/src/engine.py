import datetime
import edinet_tools
from loguru import logger
from src.infra.db import db_manager
from src.service.ingestor import DataIngestor
from src.queries.repository import DataRepository
from src.infra.migrations import MigrationManager

class JPEDINETEngine:
    """
    Orchestration layer that coordinates Ingestion and Repository services.
    """
    def __init__(self):
        self.ingestor = DataIngestor()
        self.repo = DataRepository()
        self._init_db()

    def _init_db(self):
        MigrationManager.apply_migrations()

    def sync_market(
        self,
        days: int = 30,
        end_date: datetime.date = None,
        session_id: str = "market-sync",
        max_workers: int = 5,
    ):
        logger.info(f"🚀 Launching Syncing market for the last {days} days...")
        if end_date is None:
            end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=days - 1)

        all_docs = []
        current_date = start_date
        while current_date <= end_date:
            try:
                docs = self.repo.get_documents_with_cache(current_date)
                if docs:
                    all_docs.extend(docs)
            except Exception as e:
                logger.error(f"❌ Failed to fetch list for {current_date}: {e}", exc_info=True)
            current_date += datetime.timedelta(days=1)

        if not all_docs:
            logger.info("No documents found.")
            return

        # Delegate processing to the Ingestor
        self.ingestor.process_docs_concurrently(all_docs, session_id, max_workers)
        self._vacuum_db()

    def sync_company(
        self, ticker: str, days: int = 30, session_id: str = "manual", max_workers: int = 5
    ):
        logger.info(f"🔍 Syncing JP Company {ticker} (Last {days} days)...")
        try:
            entity = edinet_tools.entity(ticker)
            docs = entity.documents(days=days)
            if not docs:
                logger.info(f"No documents found for {ticker}.")
                return
            self.ingestor.process_docs_concurrently(docs, session_id, max_workers)
        except Exception as e:
            logger.error(f"❌ Failed to sync {ticker}: {e}", exc_info=True)
        self._vacuum_db()

    def backfill_missing_data(self, max_workers: int = 5):
        self.ingestor.backfill_missing_data(max_workers=max_workers)
        self._vacuum_db()

    def _vacuum_db(self):
        logger.info("Running DB VACUUM to reclaim storage space...")
        try:
            with db_manager.connect_master() as conn:
                conn.execute("VACUUM;")
            logger.info("VACUUM completed successfully.")
        except Exception as e:
            logger.error(f"Failed to execute VACUUM: {e}")
