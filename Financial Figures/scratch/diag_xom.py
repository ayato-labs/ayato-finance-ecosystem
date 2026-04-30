import duckdb

from src.core.config import settings


def diagnose_xom():
    conn = duckdb.connect(str(settings.DB_PATH_US))
    conn.execute(f"ATTACH '{settings.DB_PATH_JP}' AS jp")
    audit_db = settings.DATA_DIR / "audit" / "traceability.duckdb"
    conn.execute(f"ATTACH '{audit_db}' AS audit")

    # Check what tags are in the US DB for XOM
    # XOM CIK is 0000034088 (verified in code)
    print("Tags for XOM (CIK 0000034088):")
    res = conn.execute("""
        SELECT f.taxonomy, f.tag, f.label, f.value, f.end_date, m.target_label
        FROM company_facts f
        LEFT JOIN audit.mapping_audit m ON m.source_tag = CONCAT('US:', f.tag)
        WHERE f.cik = '0000034088'
        AND f.end_date = '2025-12-31'
        AND m.target_label IS NOT NULL
    """).df()
    print(res)


if __name__ == "__main__":
    diagnose_xom()
