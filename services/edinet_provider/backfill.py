import sys
from loguru import logger
from src.engine import JPEDINETEngine
from src.infra.tracing import trace_execution
from src.infra.logging_config import setup_logging


@trace_execution
def main():
    setup_logging()
    logger.info("Starting Narrative & Fact Backfill Job...")

    engine = JPEDINETEngine()
    # We target documents with missing narratives or facts
    engine.backfill_missing_data(max_workers=10)
    logger.info("Data Backfill Job completed successfully.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception(f"Backfill job failed: {e}")
        sys.exit(1)
