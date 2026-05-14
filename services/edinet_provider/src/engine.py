import datetime
import logging

from loguru import logger

from src.ingestor.service.ingestor import DataIngestor
from src.shared.infra.db import db_manager
from src.shared.infra.migrations import MigrationManager
from src.shared.queries.repository import DataRepository

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
        days: int = 30,
        end_date: datetime.date | None = None,
        session_id: str = "market-sync",
        max_workers: int = 5,
        run_vacuum: bool = True,
    ):
        """
        Synchronizes market data from EDINET for a specified period.
        - Checks local registry to avoid redundant downloads.
        - Parallel ingestion for speed.
        """
        if end_date is None:
            end_date = datetime.date.today()

        start_date = end_date - datetime.timedelta(days=days - 1)
        logger.info(f"🚀 Launching Syncing market from {start_date} to {end_date} ({days} days)...")

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

    def _vacuum_db(self):
        """Maintenance: Reclaim space and optimize indexes."""
        logger.info("Running database maintenance (VACUUM)...")
        try:
            with db_manager.connect_master() as conn:
                conn.execute("VACUUM")
                conn.execute("ANALYZE")
            logger.info("✅ Database maintenance complete.")
        except Exception as e:
            logger.warning(f"Maintenance failed (possible lock contention): {e}")

    def backfill_missing(self, max_workers: int = 5):
        """Public entry point for identifying gaps and filling them."""
        self.ingestor.backfill_missing_data(max_workers=max_workers)
