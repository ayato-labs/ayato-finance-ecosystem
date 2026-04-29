import duckdb

from src.core.config import settings


def verify():
    audit_db = str(settings.DATA_DIR / "audit" / "traceability.duckdb")
    conn = duckdb.connect(audit_db, read_only=True)

    print("=== Latest AI Mapping Entries ===")
    res = conn.execute("""
        SELECT source_tag, target_label, model, reasoning, confidence 
        FROM mapping_audit 
        ORDER BY id DESC LIMIT 5
    """).fetchall()

    if not res:
        print("No mapping entries found at all!")
        return

    for r in res:
        print(f"Source: {r[0]} -> Target: {r[1]} ({r[2]})")
        print(f"  Reasoning: {r[3]}")
        print(f"  Confidence: {r[4]}")

    print("\n=== Valid Target Labels in Settings ===")
    print(settings.TARGET_LABELS)


if __name__ == "__main__":
    verify()
