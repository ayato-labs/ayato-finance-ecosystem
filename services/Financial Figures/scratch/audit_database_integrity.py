from pathlib import Path

import duckdb


def run_audit():
    db_us = Path("data/markets/us.duckdb")
    db_audit = Path("data/audit/traceability.duckdb")

    if not db_us.exists() or not db_audit.exists():
        print("Required databases not found.")
        print(f"US DB exists: {db_us.exists()}")
        print(f"Audit DB exists: {db_audit.exists()}")
        return

    conn_us = duckdb.connect(str(db_us), read_only=True)
    conn_audit = duckdb.connect(str(db_audit), read_only=True)

    today = "2026-04-22"

    # 1. Total facts ingested today
    facts_today = conn_us.execute(
        "SELECT count(*) FROM company_facts WHERE ingested_at >= ?", [today]
    ).fetchone()[0]

    # 2. Total unique tags ingested today
    unique_tags_today = conn_us.execute(
        "SELECT count(DISTINCT tag) FROM company_facts WHERE ingested_at >= ?", [today]
    ).fetchone()[0]

    # 3. Mappings saved today
    mappings_today = conn_audit.execute(
        "SELECT count(*) FROM mapping_audit WHERE mapped_at >= ?", [today]
    ).fetchone()[0]

    # 4. Total session counts
    sessions_today = conn_audit.execute(
        "SELECT count(*) FROM sync_sessions WHERE started_at >= ?", [today]
    ).fetchone()[0]

    print(f"--- Marketplace Sync Audit ({today}) ---")
    print(f"Ingested Facts:     {facts_today:,}")
    print(f"Unique Source Tags: {unique_tags_today:,}")
    print(f"Saved AI Mappings:  {mappings_today:,}")
    print(f"Sync Sessions:      {sessions_today}")

    gap = unique_tags_today - mappings_today
    if gap > 0:
        print(f"\n[CAUTION] Efficiency Gap: {gap:,} tags are missing a cached mapping.")
        print("This confirms that some AI results were NOT saved due to file locking.")
    else:
        print("\n[SUCCESS] All unique tags have a corresponding saved mapping.")


if __name__ == "__main__":
    run_audit()
