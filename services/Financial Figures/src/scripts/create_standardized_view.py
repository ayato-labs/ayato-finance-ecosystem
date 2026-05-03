import duckdb

from src.core.config import settings


def create_view():
    us_db = settings.DB_PATH_US
    audit_db = settings.DATA_DIR / "audit" / "traceability.duckdb"

    print(f"Connecting to {us_db}...")
    conn = duckdb.connect(str(us_db))

    # Attach audit database
    print(f"Attaching {audit_db} as 'audit'...")
    conn.execute(f"ATTACH '{audit_db}' AS audit")

    # Create the Standardized Financials View
    # Note: We filter out 'Other' to show only the mapped standard items.
    view_sql = """
    CREATE OR REPLACE VIEW v_standardized_financials AS
    SELECT
        t.ticker,
        t.name as company_name,
        m.target_label,
        m.source_tag,
        f.value,
        f.unit,
        f.end_date,
        f.fiscal_year,
        f.fiscal_period,
        f.form,
        f.filed_date,
        m.reasoning
    FROM company_facts f
    JOIN tickers t ON f.cik = t.cik
    JOIN audit.mapping_audit m ON m.source_tag = 'US:' || f.tag
    WHERE m.target_label != 'Other'
    """

    print("Creating view 'v_standardized_financials'...")
    conn.execute(view_sql)

    # Demonstrate the result
    print("\n--- Standardized Financials Prototype Output (Sample) ---")
    sample_items = conn.execute("""
        SELECT ticker, target_label, value, unit, end_date
        FROM v_standardized_financials
        WHERE target_label IN ('NetSales', 'NetProfit', 'TotalAssets')
        AND fiscal_period = 'FY'
        ORDER BY ticker, end_date DESC, target_label
        LIMIT 15
    """).df()

    print(sample_items.to_string())

    # Export to Parquet for verification
    export_path = settings.DATA_DIR / "standardized_prototype.parquet"
    print(f"\nExporting full view to {export_path}...")
    conn.execute(f"COPY v_standardized_financials TO '{export_path}' (FORMAT PARQUET)")

    conn.close()
    print("\nPrototype Complete!")


if __name__ == "__main__":
    create_view()
