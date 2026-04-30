import logging

from src.edinet.sync_worker import EDINETSyncWorker


def run_backfill():
    # Configure high-density logging for visibility
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger("BackfillRunner")

    logger.info("Starting EDINET Backfill (7 days) with specialized AI mapping...")

    worker = EDINETSyncWorker()
    try:
        # This will:
        # 1. Update ticker master
        # 2. Fetch doc list for last 3 days
        # 3. Filter for listed companies
        # 4. Download and parse CSVs
        # 5. Map tags using the new J-Quants V2 specialized AI mapper
        # 6. Save to edinet.duckdb with extracted fiscal year/period
        worker.run_backfill(days=3)
        logger.info("Backfill completed successfully.")
    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)


if __name__ == "__main__":
    run_backfill()
