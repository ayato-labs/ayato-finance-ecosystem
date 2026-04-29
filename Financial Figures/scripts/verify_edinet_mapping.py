import logging

from dotenv import load_dotenv

from src.core.config import settings
from src.mappers.ai_mapper import AIMapper


def verify_mapping():
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    mapper = AIMapper()

    # Test cases: (Market, Tag, Description/Name)
    test_cases = [
        ("EDINET", "jppfs_cor:NetSales", "売上高"),
        ("EDINET", "jppfs_cor:OperatingIncome", "営業利益"),
        ("EDINET", "jppfs_cor:OrdinaryIncome", "経常利益"),
        ("EDINET", "jppfs_cor:NetIncome", "当期純利益"),
        ("EDINET", "jppfs_cor:EarningsPerShareSummary", "1株当たり当期純利益"),
        ("EDINET", "jppfs_cor:TotalAssets", "資産合計"),
        ("EDINET", "jppfs_cor:NetAssets", "純資産合計"),
        ("EDINET", "jppfs_cor:EquityToAssetRatioSummary", "自己資本比率"),
        (
            "EDINET",
            "jppfs_cor:CashFlowsFromOperatingActivities",
            "営業活動によるキャッシュ・フロー",
        ),
    ]

    print("\n=== Starting EDINET Mapping Verification ===")

    # Use batch mapping for efficiency and to test the batch logic
    tags_to_map = [(t, d) for m, t, d in test_cases]
    results = mapper.map_tags_bulk("EDINET", tags_to_map, "verify-session")

    success_count = 0
    for r in results:
        tag = r["source_tag"].split(":", 1)[1]
        label = r["mapped_label"]
        print(f"Tag: {tag:40} -> Label: {label:20} | Reason: {r['reasoning']}")

        if label in settings.JQUANTS_V2_LABELS:
            success_count += 1
        elif label == "Other":
            print(f"  [WARNING] Mapped to 'Other' for {tag}")
        else:
            print(f"  [ERROR] Invalid label returned: {label}")

    print(f"\nVerification Complete. {success_count}/{len(test_cases)} mapped to J-Quants schema.")


if __name__ == "__main__":
    verify_mapping()
