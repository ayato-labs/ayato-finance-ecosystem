from datetime import datetime
from pathlib import Path

import duckdb

DB_PATH = Path("data/audit/traceability.duckdb")


def report():
    if not DB_PATH.exists():
        print("Traceability DB not found.")
        return

    conn = duckdb.connect(str(DB_PATH), read_only=True)

    # Get current session start time
    session = conn.execute(
        "SELECT started_at FROM sync_sessions WHERE status = 'RUNNING' ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    if not session:
        print("No running session found.")
        return

    start_time = session[0]
    now = datetime.now()
    elapsed_seconds = (now - start_time).total_seconds()

    # Count tickers updated in THIS session
    count = conn.execute(
        "SELECT count(*) FROM sync_progress WHERE last_synced_at >= ?", [start_time]
    ).fetchone()[0]

    # Rate calculation
    rate = count / elapsed_seconds if elapsed_seconds > 0 else 0

    # Total targets (approximate based on typical market size if us.duckdb is locked)
    # We can try to get the total from sync_progress table itself (all symbols known)
    total_known = conn.execute("SELECT count(*) FROM sync_progress").fetchone()[0]

    remaining = total_known - count
    estimated_seconds_left = remaining / rate if rate > 0 else 0

    print("--- Detailed Time Estimation ---")
    print(f"Session Start: {start_time}")
    print(f"Elapsed Time: {elapsed_seconds / 60:.1f} minutes")
    print(f"Tickers Processed: {count:,} / {total_known:,}")
    print(f"Current Rate: {rate * 60:.1f} tickers/minute")

    if rate > 0:
        print(
            f"Estimated Time Left: {estimated_seconds_left / 60:.1f} minutes (~{estimated_seconds_left / 3600:.1f} hours)"
        )
        print(
            f"Estimated Finish: {datetime.fromtimestamp(now.timestamp() + estimated_seconds_left).strftime('%H:%M:%S')}"
        )
    else:
        print("Rate is 0. Processing might be stalled or just starting.")


if __name__ == "__main__":
    report()
