import duckdb

from src.core.config import settings


def check_xom_joined():
    conn = duckdb.connect(str(settings.DB_PATH_US))
    conn.execute(f"ATTACH '{settings.DB_PATH_JP}' AS jp")
    audit_db = settings.DATA_DIR / "audit" / "traceability.duckdb"
    conn.execute(f"ATTACH '{audit_db}' AS audit")

    conn.execute("""
        CREATE OR REPLACE VIEW v_standardized_financials AS
        SELECT 
            'US' as market, t.ticker as symbol, t.name as company_name, 
            m.target_label, f.value, f.unit, f.end_date as period_date, 
            f.fiscal_year, m.reasoning
        FROM main.company_facts f
        JOIN main.tickers t ON f.cik = t.cik
        JOIN audit.mapping_audit m ON m.source_tag = CONCAT('US:', f.tag)
        WHERE m.target_label != 'Other'
    """)

    print("Target labels for XOM on 2025-12-31:")
    df = conn.execute("""
        SELECT target_label, value, period_date
        FROM v_standardized_financials
        WHERE symbol = 'XOM' AND period_date = '2025-12-31'
    """).df()
    print(df)


if __name__ == "__main__":
    check_xom_joined()
