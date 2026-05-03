import logging
import time

from src.core.audit_manager import audit_manager
from src.mappers.ai_mapper import AIMapper

# Setup logging to see the output
logging.basicConfig(level=logging.INFO)


def test_bulk_mapping():
    print("=== AI Mapper Bulk Verification Test ===")
    mapper = AIMapper()

    # Start a test session
    session_id = audit_manager.start_session(market="TEST_BULK")
    print(f"Test Session ID: {session_id}")

    # Test Data: Multiple tags
    test_tags = [
        ("us-gaap:NetIncomeLoss", "Net income"),
        ("us-gaap:Revenues", "Total revenues"),
        ("us-gaap:Assets", "Total assets"),
        ("us-gaap:Liabilities", "Total liabilities"),
        ("us-gaap:CashAndCashEquivalentsAtCarryingValue", "Cash and cash equivalents"),
    ]

    print(f"Starting bulk mapping of {len(test_tags)} tags...")
    start_time = time.perf_counter()
    results = mapper.map_tags_bulk("US", test_tags, session_id, batch_size=2)
    end_time = time.perf_counter()

    print(f"\nBulk Mapping completed in {end_time - start_time:.2f} seconds.")
    print(f"Total results: {len(results)}")

    for r in results:
        print(f" - {r.get('tag_id')}: {r.get('mapped_label')} ({r.get('confidence')})")

    # Clean up / End session
    audit_manager.end_session(session_id, "SUCCESS", len(results), 0)
    print("\nTest Complete.")


if __name__ == "__main__":
    test_bulk_mapping()
