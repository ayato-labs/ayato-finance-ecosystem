import sys
import os
from pathlib import Path

# Add project root to sys.path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from loguru import logger
from src.core.logging import setup_logging
from src.providers.edinet.sync_worker import EDINETSyncWorker

def main():
    setup_logging()
    logger.info("Starting EDINET Standalone Sync...")
    try:
        worker = EDINETSyncWorker()
        # Default to incremental sync for efficiency
        worker.run_incremental_sync()
        logger.info("EDINET Sync Completed successfully.")
    except Exception as e:
        logger.error(f"EDINET Sync Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
