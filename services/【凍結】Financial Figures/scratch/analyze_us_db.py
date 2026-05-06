from pathlib import Path

import duckdb

db_path = r"C:\Users\saiha\My_Service\programing\finance\Financial Figures\data\markets\us.duckdb"


def analyze_us_db():
    if not Path(db_path).exists():
        print(f"Error: Database file not found at {db_path}")
        return

    conn = duckdb.connect(db_path, read_only=True)

    print("--- US Database Analysis (SEC EDGAR Data) ---")

    # 1. Total tickers (from tickers table)
    total_tickers = conn.execute("SELECT count(*) FROM tickers").fetchone()[0]
    print(f"Total Tickers in master: {total_tickers}")

    # 2. Tickers with facts
    tickers_with_facts = conn.execute("SELECT count(distinct cik) FROM company_facts").fetchone()[0]
    print(f"Tickers with Fact Data (CIK count): {tickers_with_facts}")

    # 3. Total records
    total_records = conn.execute("SELECT count(*) FROM company_facts").fetchone()[0]
    print(f"Total Fact Records: {total_records}")

    # 4. Date range
    date_range = conn.execute(
        "SELECT min(filed_date), max(filed_date) FROM company_facts"
    ).fetchone()
    print(f"Date Range (Filed Date): {date_range[0]} to {date_range[1]}")

    # 5. Taxonomy distribution
    print("\nTaxonomy Distribution:")
    taxonomies = conn.execute(
        "SELECT taxonomy, count(*) as count FROM company_facts GROUP BY taxonomy ORDER BY count DESC"
    ).fetchall()
    for tax, count in taxonomies:
        print(f"  {tax}: {count}")

    # 6. Top 10 CIKs by data density
    print("\nTop 10 Companies by data volume (CIK):")
    top_ciks = conn.execute(
        "SELECT cik, count(*) as count FROM company_facts GROUP BY cik ORDER BY count DESC LIMIT 10"
    ).fetchall()
    for cik, count in top_ciks:
        # Try to find ticker for this CIK
        ticker_res = conn.execute("SELECT ticker FROM tickers WHERE cik = ?", (cik,)).fetchone()
        ticker = ticker_res[0] if ticker_res else "Unknown"
        print(f"  {ticker} (CIK:{cik}): {count} records")

    # 7. Common Labels
    print("\nTop 20 Labels in DB:")
    labels = conn.execute(
        "SELECT label, count(*) as count FROM company_facts GROUP BY label ORDER BY count DESC LIMIT 20"
    ).fetchall()
    for label, count in labels:
        print(f"  {label}: {count}")

    # 8. Forms distribution
    print("\nForms Distribution (10-K, 10-Q, etc.):")
    forms = conn.execute(
        "SELECT form, count(*) as count FROM company_facts GROUP BY form ORDER BY count DESC"
    ).fetchall()
    for form, count in forms:
        print(f"  {form}: {count}")

    conn.close()


if __name__ == "__main__":
    analyze_us_db()
