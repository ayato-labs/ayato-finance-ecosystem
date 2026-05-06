import sys
from loguru import logger
from src.engine import JPEDINETEngine

def main():
    # Logging is initialized on import of src.engine -> src.core.logging_config
    logger.info("Starting Narrative & Fact Backfill Job...")
    
    engine = JPEDINETEngine()
    try:
        # We target documents with missing narratives or facts
        engine.backfill_missing_data(max_workers=10) # slightly lower concurrency for stability
        logger.info("Data Backfill Job completed successfully.")
    except Exception as e:
        logger.error(f"Backfill Job failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
