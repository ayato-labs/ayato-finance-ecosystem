import time
from pathlib import Path

import duckdb

DB_PATH = Path("data/markets/us.duckdb")


def verify():
    conn = duckdb.connect(str(DB_PATH), read_only=True)

    print("--- Schema Verification ---")
    cols = conn.execute("DESCRIBE company_facts").fetchall()
    for col in cols:
        if col[0] in ["taxonomy", "fiscal_period", "form"]:
            print(f"Column {col[0]}: {col[1]}")

    print("\n--- Row Count Verification ---")
    count = conn.execute("SELECT count(*) FROM company_facts").fetchone()[0]
    print(f"Total Rows: {count:,}")

    print("\n--- Performance Benchmark ---")
    # A query that benefits from sorting (cik, tag, end_date)
    # and ZONEMAPs on taxonomy/fiscal_period
    queries = [
        "SELECT count(*) FROM company_facts WHERE taxonomy = 'us-gaap' AND fiscal_period = 'Q1'",
        "SELECT * FROM company_facts WHERE cik = '0000320193' AND tag = 'NetIncomeLoss' ORDER BY end_date DESC LIMIT 5",
    ]

    for q in queries:
        start = time.perf_counter()
        res = conn.execute(q).fetchall()
        duration = time.perf_counter() - start
        print(f"Query: {q}")
        print(f"Result count: {len(res)}, Time: {duration:.4f}s")


if __name__ == "__main__":
    verify()
