from datetime import datetime
from pathlib import Path

import duckdb

# Paths
DATA_DIR = Path(r"C:\Users\saiha\My_Service\programing\finance\Financial Figures\data")
US_DB = DATA_DIR / "markets" / "us.duckdb"
JP_DB = DATA_DIR / "markets" / "jp.duckdb"
EDINET_DB = DATA_DIR / "edinet.duckdb"


def analyze_db(name, path, table, code_col, date_col):
    print(f"\n=== {name} Database Analysis ===")
    if not path.exists():
        print(f"Error: Database {path} not found.")
        return

    try:
        conn = duckdb.connect(str(path), read_only=True)

        # Total companies
        companies = conn.execute(f"SELECT count(distinct {code_col}) FROM {table}").fetchone()[0]
        # Total records
        records = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        # Date range
        dates = conn.execute(f"SELECT min({date_col}), max({date_col}) FROM {table}").fetchone()

        print(f"  Path: {path.name}")
        print(f"  Companies: {companies:,}")
        print(f"  Total Records: {records:,}")
        print(f"  Date Range: {dates[0]} to {dates[1]}")

        # Top 5 by density
        print("  Top 5 Companies (Density):")
        top = conn.execute(
            f"SELECT {code_col}, count(*) as c FROM {table} GROUP BY {code_col} ORDER BY c DESC LIMIT 5"
        ).fetchall()
        for c, count in top:
            print(f"    - {c}: {count:,} records")

        # Recent data check (latest 3 days)
        recent = conn.execute(
            f"SELECT count(*) FROM {table} WHERE {date_col} >= (SELECT max({date_col}) FROM {table}) - INTERVAL '3 days'"
        ).fetchone()[0]
        print(f"  Recent Records (Last 3 days of data): {recent:,}")

        conn.close()
    except Exception as e:
        print(f"  Error analyzing {name}: {e}")


def main():
    print(f"Report generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # US (SEC EDGAR)
    analyze_db("US (SEC EDGAR)", US_DB, "company_facts", "cik", "filed_date")

    # JP (J-Quants)
    analyze_db("JP (J-Quants)", JP_DB, "company_facts", "code", "disclosed_date")

    # EDINET (JP Statutory)
    analyze_db("EDINET (Statutory)", EDINET_DB, "company_facts", "code", "disclosed_date")


if __name__ == "__main__":
    main()
