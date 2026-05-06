import sys
from loguru import logger
from src.engine import JPEDINETEngine
from src.core.tracing import trace_execution

@trace_execution
def main():
    logger.info("Starting Narrative & Fact Backfill Job...")
    
    engine = JPEDINETEngine()
    # We target documents with missing narratives or facts
    engine.backfill_missing_data(max_workers=10)
    logger.info("Data Backfill Job completed successfully.")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(1)
