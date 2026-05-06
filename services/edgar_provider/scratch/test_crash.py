import sys
import os
sys.path.insert(0, os.path.abspath("."))

import traceback
from loguru import logger

logger.add("scratch/test_crash.log", mode="w")

try:
    from src.engine import USEngine
    engine = USEngine()
    engine.ingest_bulk_data("test_session")
except Exception as e:
    logger.error("Exception caught!")
    traceback.print_exc()
    sys.exit(1)
