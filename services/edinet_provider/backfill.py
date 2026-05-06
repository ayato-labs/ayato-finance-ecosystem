import sys
from loguru import logger
from src.engine import JPEDINETEngine

def main():
    logger.info("Starting Narrative & Fact Backfill Job...")
    
    engine = JPEDINETEngine()
    try:
        # We target documents with missing narratives or facts
        engine.backfill_missing_data(max_workers=10)
        logger.info("Data Backfill Job completed successfully.")
    except Exception as e:
        logger.error("Backfill Job failed: {error}", error=e)
        sys.exit(1)

if __name__ == "__main__":
    main()
