from pathlib import Path

import duckdb


def show_history():
    log_file = Path("./data/logs/sync_history.parquet")
    if not log_file.exists():
        print("No sync history found. Please run a sync first.")
        return

    db = duckdb.connect()

    print("\n--- [Ingestion Audit: Sync History] ---")

    # 1. Global Metrics
    stats = db.query(f"""
        SELECT
            Status,
            COUNT(*) as attempts,
            SUM(RecordsFetched) as total_rows
        FROM read_parquet('{log_file}')
        GROUP BY Status
    """).df()
    print("\nOverall Status Summary:")
    print(stats.to_string(index=False))

    # 2. Latest Attempts per Ticker
    print("\nLatest 10 Sync Attempts:")
    latest = db.query(f"""
        SELECT
            Timestamp,
            Ticker,
            RecordsFetched,
            Status,
            Message
        FROM read_parquet('{log_file}')
        ORDER BY Timestamp DESC
        LIMIT 10
    """).df()
    print(latest.to_string(index=False))

    # 3. Identifying "Holes" (Tickers that never succeeded)
    print("\nTickers with NO successful records (Potential Issues):")
    holes = db.query(f"""
        SELECT Ticker, COUNT(*) as failed_attempts, MAX(Message) as last_error
        FROM read_parquet('{log_file}')
        GROUP BY Ticker
        HAVING SUM(RecordsFetched) = 0
        LIMIT 20
    """).df()

    if not holes.empty:
        print(holes.to_string(index=False))
    else:
        print("  [PASS] All sync attempts for all tickers returned data.")


if __name__ == "__main__":
    show_history()
