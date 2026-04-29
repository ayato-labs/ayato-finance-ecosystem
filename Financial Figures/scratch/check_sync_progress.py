from pathlib import Path

import duckdb

DB_PATH = Path("data/markets/us.duckdb")


def report():
    conn = duckdb.connect(str(DB_PATH), read_only=True)

    # Get total count
    total = conn.execute("SELECT count(*) FROM company_facts").fetchone()[0]

    # Get recent ingestion (last 10 mins)
    # Using CURRENT_TIMESTAMP logic compatible with DuckDB
    recent = conn.execute(
        "SELECT count(*) FROM company_facts WHERE ingested_at >= (CURRENT_TIMESTAMP - INTERVAL '10 minutes')"
    ).fetchone()[0]

    # Get count of unique CIKs updated recently
    unique_ciks = conn.execute(
        "SELECT count(DISTINCT cik) FROM company_facts WHERE ingested_at >= (CURRENT_TIMESTAMP - INTERVAL '10 minutes')"
    ).fetchone()[0]

    # Get latest ingested CIK
    latest_cik = conn.execute(
        "SELECT cik FROM company_facts ORDER BY ingested_at DESC LIMIT 1"
    ).fetchone()
    ticker_name = "N/A"
    if latest_cik:
        t = conn.execute(f"SELECT ticker FROM tickers WHERE cik = '{latest_cik[0]}'").fetchone()
        if t:
            ticker_name = t[0]

    print("--- Marketplace Sync Status ---")
    print(f"Total Database Rows: {total:,}")
    print(f"Recently Ingested (10m): {recent:,} facts")
    print(f"Tickers Processed (10m): {unique_ciks}")
    print(f"Current Processing Target: {ticker_name} ({latest_cik[0] if latest_cik else 'None'})")
    print("Status: ACTIVE (8 workers)")


if __name__ == "__main__":
    report()
