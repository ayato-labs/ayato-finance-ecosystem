import duckdb

from src.core.config import settings


def debug_join():
    conn = duckdb.connect(str(settings.DB_PATH_US))
    conn.execute(f"ATTACH '{settings.DB_PATH_JP}' AS jp")
    audit_db = settings.DATA_DIR / "audit" / "traceability.duckdb"
    conn.execute(f"ATTACH '{audit_db}' AS audit")

    # 1. Check a few raw tag values for XOM
    print("--- RAW TAGS FOR XOM (2025-12-31) ---")
    raw_tags = conn.execute("""
        SELECT tag, taxonomy, label
        FROM company_facts
        WHERE cik = '0000034088' AND end_date = '2025-12-31'
        AND tag IN ('NetIncomeLoss', 'Revenues', 'SalesRevenueNet')
    """).df()
    print(raw_tags)

    # 2. Check mapping_audit entries
    print("\n--- MAPPING AUDIT ENTRIES ---")
    mappings = conn.execute("""
        SELECT source_tag, target_label
        FROM audit.mapping_audit
        WHERE source_tag LIKE '%NetIncomeLoss%'
           OR source_tag LIKE '%Revenues%'
           OR source_tag LIKE '%SalesRevenueNet%'
    """).df()
    print(mappings)

    # 3. Test CONCAT join specifically
    print("\n--- TEST CONCAT JOIN ---")
    test_join = conn.execute("""
        SELECT f.tag, m.source_tag, m.target_label
        FROM company_facts f
        JOIN audit.mapping_audit m ON m.source_tag = 'US:' || f.tag
        WHERE f.cik = '0000034088' AND f.end_date = '2025-12-31'
        AND f.tag = 'NetIncomeLoss'
    """).df()
    print(test_join)


if __name__ == "__main__":
    debug_join()
