import time
import pandas as pd
from loguru import logger
from src.core.db import db_manager
from src.core.config import settings
from src.core.audit_manager import audit_manager
from src.engines.us_engine import USEngine
from src.engines.jp_engine import JPEngine

def profile_us_ingestion_overhead():
    logger.info("Profiling US Engine Ingestion Overhead...")
    us_engine = USEngine()
    
    # Simulate a typical large US fact JSON (e.g., 5000 facts)
    num_facts = 5000
    mock_facts = {
        "cik": "0000320193",
        "facts": {
            "us-gaap": {
                f"Tag{i}": {
                    "label": f"Label {i}",
                    "units": {
                        "USD": [{"val": 100, "end": "2023-12-31", "accn": "1", "fy": 2023, "fp": "FY", "form": "10-K", "filed": "2024-01-01"}]
                    }
                } for i in range(num_facts)
            }
        }
    }
    
    start_time = time.perf_counter()
    # Profile python-side processing (flattening + validation)
    us_engine.ingest_facts("AAPL", mock_facts, "profile-session")
    duration = time.perf_counter() - start_time
    
    logger.info(f"US Ingestion for {num_facts} facts took {duration:.4f}s ({duration/num_facts:.6f}s/fact)")

def profile_unmapped_tag_discovery():
    logger.info("Profiling Unmapped Tag Discovery Overhead...")
    # This simulates the logic inside BatchSyncService._queue_unmapped_tags
    # which runs on the single-threaded DBWriter
    
    market = "US"
    symbol = "AAPL"
    
    start_time = time.perf_counter()
    
    # 1. Ticker lookup
    with db_manager.connect(settings.DB_PATH_US, read_only=True) as conn:
        res = conn.execute("SELECT cik FROM tickers WHERE ticker = ?", [symbol]).fetchone()
        cik = res[0] if res else "0000320193"
        
    # 2. Get distinct tags from facts (This is the heavy part)
    with db_manager.connect(settings.DB_PATH_US, read_only=True) as conn:
        # Pre-filter by CIK to simulate real workload
        raw_tags = conn.execute("SELECT DISTINCT tag, label FROM company_facts WHERE cik = ?", [cik]).fetchall()
    
    discovery_time = time.perf_counter() - start_time
    
    # 3. Audit check
    start_audit = time.perf_counter()
    source_tags = [f"{market}:{t[0]}" for t in raw_tags]
    unmapped = audit_manager.get_unmapped_tags(market, source_tags)
    audit_time = time.perf_counter() - start_audit
    
    total_time = time.perf_counter() - start_time
    
    logger.info(f"Tag discovery for {len(raw_tags)} tags: {discovery_time:.4f}s")
    logger.info(f"Audit check for {len(source_tags)} tags: {audit_time:.4f}s")
    logger.info(f"Total discovery overhead: {total_time:.4f}s")

if __name__ == "__main__":
    try:
        profile_us_ingestion_overhead()
    except Exception as e:
        logger.warning(f"US Ingestion profile failed (likely DB missing): {e}")
        
    try:
        profile_unmapped_tag_discovery()
    except Exception as e:
        logger.warning(f"Tag discovery profile failed: {e}")
