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
        self._db_initialized = False

    def _ensure_db_initialized(self):
        """Lazy initialization: only runs migrations when a write action is requested."""
        if not self._db_initialized:
            logger.info("Initializing database and checking migrations...")
            try:
                MigrationManager.apply_migrations()
                self._db_initialized = True
            except Exception as e:
                logger.critical(f"Failed to initialize database: {e}")
                raise

    def sync_market(
        self,
        days: int = 30,
        end_date: datetime.date = None,
        session_id: str = "market-sync",
        max_workers: int = 5,
        run_vacuum: bool = False,
    ):
        self._ensure_db_initialized()
        if end_date is None:
            end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=days - 1)

        logger.info(f"🚀 Launching Syncing market from {start_date} to {end_date} ({days} days)...")

        all_docs = []
        current_date = start_date
        while current_date <= end_date:
            try:
                docs = self.repo.get_documents_with_cache(current_date)
                if docs:
                    all_docs.extend(docs)
                    logger.debug(f"Found {len(docs)} docs for {current_date}")
            except Exception as e:
                logger.error(f"❌ Failed to fetch list for {current_date}: {e}")
                # We log and continue to the next day to be resilient
            current_date += datetime.timedelta(days=1)

        if not all_docs:
            logger.warning(f"No documents discovered in the range {start_date} to {end_date}.")
            return

        logger.info(f"Discovery phase complete. Total candidates: {len(all_docs)}")

        try:
            # Delegate processing to the Ingestor
            self.ingestor.process_docs_concurrently(all_docs, session_id, max_workers)
        except Exception as e:
            logger.critical(f"Market sync pipeline failed: {e}", exc_info=True)
            raise
        finally:
            if run_vacuum:
                self._vacuum_db()

    def sync_company(
        self,
        ticker: str,
        days: int = 30,
        session_id: str = "manual",
        max_workers: int = 5,
        run_vacuum: bool = False,
    ):
        logger.info(f"🔍 Syncing JP Company {ticker} (Last {days} days)...")
        try:
            entity = edinet_tools.entity(ticker)
            docs = entity.documents(days=days)
            if not docs:
                logger.info(f"No documents found for {ticker}.")
                return
            logger.info(f"Found {len(docs)} filings for {ticker}. Starting ingestion...")
            self.ingestor.process_docs_concurrently(docs, session_id, max_workers)
        except Exception as e:
            logger.error(f"❌ Failed to sync {ticker}: {e}", exc_info=True)
            raise
        finally:
            if run_vacuum:
                self._vacuum_db()

    def backfill_missing_data(self, max_workers: int = 5):
        self._ensure_db_initialized()
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
