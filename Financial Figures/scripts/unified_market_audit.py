import duckdb
import pandas as pd

from src.core.config import settings


def run_unified_audit():
    print("\n=== Unified Market Data Audit (J-Quants vs EDINET) ===")

    jp_db = settings.DB_PATH_JP
    edinet_db = settings.DB_PATH_EDINET

    if not jp_db.exists() or not edinet_db.exists():
        print(f"Error: Database missing. JP: {jp_db.exists()}, EDINET: {edinet_db.exists()}")
        return

    # 1. Label Coverage Comparison
    print("\n[1] Label Distribution (Top 15)")

    # J-Quants
    conn_jp = duckdb.connect(str(jp_db), read_only=True)
    df_jp = conn_jp.execute("""
        SELECT label, count(*) as count 
        FROM company_facts 
        GROUP BY label 
        ORDER BY count DESC 
        LIMIT 15
    """).df()
    conn_jp.close()

    # EDINET
    conn_edinet = duckdb.connect(str(edinet_db), read_only=True)
    df_edinet = conn_edinet.execute("""
        SELECT label, count(*) as count 
        FROM company_facts 
        GROUP BY label 
        ORDER BY count DESC 
        LIMIT 15
    """).df()
    conn_edinet.close()

    combined_labels = pd.merge(
        df_jp, df_edinet, on="label", how="outer", suffixes=("_JQ", "_EDINET")
    ).fillna(0)
    print(combined_labels.to_string(index=False))

    # 2. Ticker Intersection
    conn_jp = duckdb.connect(str(jp_db), read_only=True)
    tickers_jp = set(conn_jp.execute("SELECT DISTINCT code FROM company_facts").df()["code"])
    conn_jp.close()

    conn_edinet = duckdb.connect(str(edinet_db), read_only=True)
    tickers_edinet = set(
        conn_edinet.execute("SELECT DISTINCT code FROM company_facts").df()["code"]
    )
    conn_edinet.close()

    intersection = tickers_jp.intersection(tickers_edinet)
    print("\n[2] Ticker Coverage")
    print(f"  J-Quants Tickers: {len(tickers_jp):,}")
    print(f"  EDINET Tickers:   {len(tickers_edinet):,}")
    print(f"  Intersection:     {len(intersection):,} (Companies with data from both)")

    # 3. Value Consistency Check (Sample for a few common tickers)
    if intersection:
        print("\n[3] Value Consistency (Sample: NetSales for top intersected companies)")
        sample_tickers = list(intersection)[:5]

        # Attach both DBs to one connection for comparison
        conn = duckdb.connect(":memory:")
        conn.execute(f"ATTACH '{jp_db}' AS jp (READ_ONLY)")
        conn.execute(f"ATTACH '{edinet_db}' AS edinet (READ_ONLY)")

        comparison = conn.execute(
            f"""
            SELECT 
                j.code, 
                j.disclosed_date, 
                j.value as jq_val, 
                e.value as ed_val,
                ABS(j.value - e.value) as diff
            FROM jp.company_facts j
            JOIN edinet.company_facts e 
              ON j.code = e.code 
             AND j.disclosed_date = e.disclosed_date 
             AND j.label = e.label
            WHERE j.label = 'NetSales'
              AND j.code IN ({",".join(["?" for _ in sample_tickers])})
            ORDER BY j.disclosed_date DESC
            LIMIT 10
        """,
            sample_tickers,
        ).df()

        if not comparison.empty:
            print(comparison.to_string(index=False))
        else:
            print("  No direct date/label matches found for NetSales in the sample intersection.")

        conn.close()


if __name__ == "__main__":
    run_unified_audit()
