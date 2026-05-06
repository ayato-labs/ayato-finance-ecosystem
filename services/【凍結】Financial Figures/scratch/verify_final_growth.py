import duckdb

from src.core.config import settings


def verify_growth_data():
    conn = duckdb.connect(str(settings.DB_PATH_US), read_only=True)
    audit_path = settings.DATA_DIR / "audit" / "traceability.duckdb"
    conn.execute(f"ATTACH '{audit_path}' AS audit")
    conn.execute(f"ATTACH '{settings.DB_PATH_JP}' AS jp")

    targets = ["TSLA", "7203"]

    for t in targets:
        print(f"\n--- Growth Metrics for {t} ---")
        q = f"""
        SELECT target_label, value, unit, period_date, reasoning
        FROM v_standardized_financials
        WHERE symbol = '{t}'
          AND target_label IN ('ResearchAndDevelopment', 'CapitalExpenditure')
        ORDER BY period_date DESC
        LIMIT 5
        """
        df = conn.execute(q).df()
        if not df.empty:
            print(df.to_string(index=False))
        else:
            print(f"No growth metrics found for {t}")


if __name__ == "__main__":
    verify_growth_data()
