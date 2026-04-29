import duckdb

from src.core.config import settings


def check_jp_joined():
    conn = duckdb.connect(str(settings.DB_PATH_US))
    conn.execute(f"ATTACH '{settings.DB_PATH_JP}' AS jp")
    audit_db = settings.DATA_DIR / "audit" / "traceability.duckdb"
    conn.execute(f"ATTACH '{audit_db}' AS audit")

    conn.execute("""
        CREATE OR REPLACE VIEW v_standardized_financials AS
        SELECT 
            'JP' as market, SUBSTR(t.code, 1, 4) as symbol, t.name as company_name, 
            m.target_label, f.value, f.unit, f.disclosed_date as period_date, 
            f.fiscal_year, m.reasoning
        FROM jp.company_facts f
        JOIN jp.tickers t ON f.code = t.code
        JOIN audit.mapping_audit m ON m.source_tag = CONCAT('JP:', f.tag)
        WHERE m.target_label != 'Other'
    """)

    print("Target labels for 1301 (JP):")
    df = conn.execute("""
        SELECT target_label, value, period_date
        FROM v_standardized_financials
        WHERE symbol = '1301'
        ORDER BY period_date DESC
    """).df()
    print(df)


if __name__ == "__main__":
    check_jp_joined()
