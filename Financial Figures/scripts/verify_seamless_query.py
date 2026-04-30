import duckdb
import pandas as pd

from src.core.config import settings


def verify_seamless_query():
    print("\n=== Seamless Query Verification (J-Quants + EDINET) ===")

    jp_db = settings.DB_PATH_JP
    edinet_db = settings.DB_PATH_EDINET

    # 1. Schema Comparison
    print("\n[1] Schema Comparison (company_facts table)")
    conn = duckdb.connect(":memory:")
    conn.execute(f"ATTACH '{jp_db}' AS jp (READ_ONLY)")
    conn.execute(f"ATTACH '{edinet_db}' AS edinet (READ_ONLY)")

    jp_schema = conn.execute("DESCRIBE jp.company_facts").df()[["column_name", "column_type"]]
    ed_schema = conn.execute("DESCRIBE edinet.company_facts").df()[["column_name", "column_type"]]

    schema_compare = pd.merge(jp_schema, ed_schema, on="column_name", suffixes=("_JP", "_EDINET"))
    print(schema_compare.to_string(index=False))

    # 2. Unified Query Execution
    print("\n[2] Unified Query (UNION ALL) - Grouped by Fiscal Period and Label")
    print("This query treats both databases as a single unified data source.")

    unified_results = conn.execute("""
        WITH unified_data AS (
            SELECT 'J-Quants' as source, code, COALESCE(fiscal_year, year(disclosed_date)) as f_year, fiscal_period, label, value
            FROM jp.company_facts
            UNION ALL
            SELECT 'EDINET' as source, code, COALESCE(fiscal_year, year(disclosed_date)) as f_year, fiscal_period, label, value
            FROM edinet.company_facts
        )
        SELECT
            label,
            f_year as fiscal_year,
            fiscal_period,
            COUNT(CASE WHEN source = 'J-Quants' THEN 1 END) as JQ_Count,
            COUNT(CASE WHEN source = 'EDINET' THEN 1 END) as ED_Count,
            AVG(value) as Avg_Value
        FROM unified_data
        WHERE label IN ('NetSales', 'OperatingProfit', 'Profit', 'TotalAssets')
        GROUP BY 1, 2, 3
        ORDER BY fiscal_year DESC, fiscal_period, label
        LIMIT 20
    """).df()

    if not unified_results.empty:
        print(unified_results.to_string(index=False))
    else:
        print("  No records found with valid fiscal_year/period yet.")

    # 3. Direct Label Consistency Test
    # Check if 'NetSales' exists in both as the same string
    print("\n[3] Label Consistency Check")
    jq_labels = set(
        conn.execute("SELECT DISTINCT label FROM jp.company_facts WHERE label = 'NetSales'").df()[
            "label"
        ]
    )
    ed_labels = set(
        conn.execute(
            "SELECT DISTINCT label FROM edinet.company_facts WHERE label = 'NetSales'"
        ).df()["label"]
    )

    if "NetSales" in jq_labels and "NetSales" in ed_labels:
        print("  SUCCESS: 'NetSales' label is identical in both databases.")
    else:
        print(
            f"  MISMATCH: JQ has 'NetSales': {'NetSales' in jq_labels}, EDINET has 'NetSales': {'NetSales' in ed_labels}"
        )

    conn.close()


if __name__ == "__main__":
    verify_seamless_query()
