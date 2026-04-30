import os

import duckdb

from src.core.config import settings


def check():
    print("=== DB Integrity Check ===")
    us_db = str(settings.DB_PATH_US)
    audit_db = str(settings.DATA_DIR / "audit" / "traceability.duckdb")

    print(f"US DB Path: {us_db} (Exists: {os.path.exists(us_db)})")
    print(f"Audit DB Path: {audit_db} (Exists: {os.path.exists(audit_db)})")

    conn = duckdb.connect(us_db)
    conn.execute(f"ATTACH '{audit_db}' AS audit")

    # Check 1: Raw Facts
    ticker_count = conn.execute("SELECT count(*) FROM tickers").fetchone()[0]
    fact_count = conn.execute("SELECT count(*) FROM company_facts").fetchone()[0]
    print(f"Tickers in US: {ticker_count}")
    print(f"Facts in US: {fact_count}")

    # Check 2: Audit Mapping
    mapping_count = conn.execute("SELECT count(*) FROM audit.mapping_audit").fetchone()[0]
    print(f"Mappings in Audit: {mapping_count}")

    # Check 3: Joined View logic
    # Try one sample record if it exists
    res = conn.execute("SELECT * FROM company_facts LIMIT 1").fetchone()
    if res:
        print(f"Sample Fact: {res}")
        # Check if the join succeeds
        tag = res[1]  # symbol is res[0], tag is res[1]
        print(f"Testing Join for tag: US:{tag}")
        joined = conn.execute(
            f"SELECT * FROM audit.mapping_audit WHERE source_tag = 'US:{tag}'"
        ).fetchall()
        print(f"Mapping entries for this tag: {len(joined)}")
    else:
        print("No raw facts to test join with.")


if __name__ == "__main__":
    check()
