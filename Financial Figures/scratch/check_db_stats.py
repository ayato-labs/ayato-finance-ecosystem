import os

import duckdb


def check_stats():
    stats = {}
    for db_name in ["us_market", "jp_market"]:
        path = f"data/{db_name}.duckdb"
        if not os.path.exists(path):
            stats[db_name] = "Not initialized"
            continue

        try:
            conn = duckdb.connect(path)
            if "us" in db_name:
                count = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
                table = "facts"
            else:
                count = conn.execute("SELECT COUNT(*) FROM statements").fetchone()[0]
                table = "statements"
            stats[db_name] = f"{count} records in {table}"
            conn.close()
        except Exception as e:
            stats[db_name] = f"Error: {e}"

    # Audit stats
    audit_path = "data/audit/traceability.duckdb"
    if os.path.exists(audit_path):
        conn = duckdb.connect(audit_path)
        mapping_count = conn.execute("SELECT COUNT(*) FROM mapping_audit").fetchone()[0]
        session_count = conn.execute("SELECT COUNT(*) FROM sync_sessions").fetchone()[0]
        stats["audit"] = f"{mapping_count} mappings, {session_count} sessions"
        conn.close()

    print("=== CURRENT DATABASE STATUS ===")
    for k, v in stats.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    check_stats()
