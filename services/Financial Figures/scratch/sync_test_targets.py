import logging

from src.core.audit_manager import audit_manager
from src.engines.jp_engine import JPEngine
from src.engines.us_engine import USEngine
from src.services.market_sync import BatchSyncService

logging.basicConfig(level=logging.INFO)


def sync_specific_targets():
    us = USEngine()
    jp = JPEngine()
    service = BatchSyncService()

    session_id = "test-extraction-pinpoint"
    audit_manager.start_session("MANUAL")

    # 1. Sync TSLA (US)
    # Ticker found 20 unmapped tags earlier, should be in cache now.
    print("\n>>> Synchronizing Tesla (TSLA) facts...")
    data_us = us.fetch_company_facts("TSLA")
    if data_us:
        us.ingest_facts("TSLA", data_us, session_id)
        service._map_unidentified_tags("US", "TSLA", session_id)
        print("--- TSLA synchronized ---")

    # 2. Sync Toyota (7203) (JP)
    print("\n>>> Synchronizing Toyota (7203) statements...")
    # JPEngine has a combined fetch_and_ingest_statements
    jp.fetch_and_ingest_statements("7203", session_id)
    service._map_unidentified_tags("JP", "7203", session_id)
    print("--- Toyota (7203) synchronized ---")


if __name__ == "__main__":
    sync_specific_targets()
