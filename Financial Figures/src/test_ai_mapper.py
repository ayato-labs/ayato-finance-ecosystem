import json

from dotenv import load_dotenv

from src.core.audit_manager import audit_manager
from src.mappers.ai_mapper import AIMapper


def test_mapping():
    # Load environment variables
    load_dotenv()

    print("=== AI Mapper Verification Test ===")
    mapper = AIMapper()

    # Start a test session
    session_id = audit_manager.start_session(market="TEST")
    print(f"Test Session ID: {session_id}")

    # Test Data: Typical US GAAP Tag
    test_cases = [
        {
            "market": "US",
            "tag": "us-gaap:NetIncomeLoss",
            "description": (
                "The portion of profit or loss for the period, net of income taxes, "
                "which is attributable to the parent."
            ),
        },
        {
            "market": "US",
            "tag": "us-gaap:SalesRevenueNet",
            "description": (
                "Total revenue from sale of goods and services rendered during "
                "the reporting period, in the normal course of business, reduced "
                "by sales returns, allowances, and discounts."
            ),
        },
    ]

    for case in test_cases:
        print(f"\nMapping Tag: {case['tag']}...")
        try:
            result = mapper.map_tag(
                market=case["market"],
                tag=case["tag"],
                description=case["description"],
                session_id=session_id,
            )
            print("Mapping Result (JSON):")
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(f"Mapping Failed: {e}")

    # End session
    audit_manager.end_session(session_id, "SUCCESS", len(test_cases), 0)
    print("\nTest Complete. Decisions saved to traceability.duckdb.")


if __name__ == "__main__":
    test_mapping()
