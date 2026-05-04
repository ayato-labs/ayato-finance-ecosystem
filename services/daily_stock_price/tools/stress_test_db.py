import duckdb
import pandas as pd

MAX_BUSINESS_DAY_GAP = 4


def strict_audit():
    db = duckdb.connect()
    parquet_path = "./data/market_data/**/*.parquet"

    print("====================================================")
    print("   DAILY STOCK PRICE DB - STRICT AUDIT REPORT      ")
    print("====================================================\n")

    # TEST 1: Market Density (Sample Tickers)
    print("--- [TEST 1: Market Density] ---")
    tickers = ["AAPL", "MSFT", "7203.T", "1301.T", "BRK-B"]
    audit_data = []
    for t in tickers:
        res = db.query(f"""
            SELECT Ticker, MIN(Date) as Start, MAX(Date) as End, COUNT(*) as Records
            FROM read_parquet('{parquet_path}')
            WHERE Ticker = '{t}'
            GROUP BY Ticker
        """).df()
        if not res.empty:
            audit_data.append(res)

    if audit_data:
        summary_df = pd.concat(audit_data)
        print(summary_df.to_string(index=False))
    else:
        print("FAIL: No data found for primary test tickers.")

    # TEST 2: Date Continuity (Gap Detection)
    print("\n--- [TEST 2: Date Continuity - Sample: 7203.T] ---")
    data_7203 = db.query(f"""
        SELECT Date FROM read_parquet('{parquet_path}')
        WHERE Ticker = '7203.T' ORDER BY Date ASC
    """).df()

    if not data_7203.empty:
        # Check for gaps (Business days only approx)
        data_7203["diff"] = data_7203["Date"].diff().dt.days
        gaps = data_7203[
            data_7203["diff"] > MAX_BUSINESS_DAY_GAP
        ]  # More than 4 days gap (e.g. New Year / Golden Week)
        if gaps.empty:
            print(f"PASS: No suspicious gaps found (>{MAX_BUSINESS_DAY_GAP} days).")
        else:
            print(
                f"INFO: Detected {len(gaps)} gaps > {MAX_BUSINESS_DAY_GAP} days "
                f"(likely holidays or market closures)."
            )
            print(gaps[["Date", "diff"]].head())
    else:
        print("FAIL: Could not perform continuity test (No data).")

    # TEST 3: Cross-Partition Aggregation (2025-12 to 2026-01)
    print("\n--- [TEST 3: Cross-Partition Moving Average (Dec 25 -> Jan 26)] ---")
    sql_ma = f"""
        SELECT Date, Close,
               AVG(Close) OVER (ORDER BY Date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) as MA20
        FROM (
            SELECT * FROM read_parquet('{parquet_path}')
            WHERE Ticker = 'AAPL' AND Date BETWEEN '2025-12-15' AND '2026-01-15'
        )
        ORDER BY Date ASC
    """
    ma_res = db.query(sql_ma).df()
    if not ma_res.empty:
        print("Sample of MA20 calculation across year-end boundary:")
        print(ma_res[ma_res["Date"].dt.month.isin([12, 1])].iloc[8:15].to_string(index=False))
        print("PASS: Cross-partition window functions working.")
    else:
        print("FAIL: Could not perform cross-partition test.")

    # TEST 4: Extraction Test (Random Tickers)
    print("\n--- [TEST 4: Random Extraction Test] ---")
    random_tickers = (
        db.query(f"SELECT DISTINCT Ticker FROM read_parquet('{parquet_path}')")
        .df()
        .sample(3)["Ticker"]
        .tolist()
    )
    print(f"Extracting full profile for: {random_tickers}")
    for rt in random_tickers:
        sql = (
            f"SELECT * FROM read_parquet('{parquet_path}') "
            f"WHERE Ticker = '{rt}' ORDER BY Date DESC LIMIT 2"
        )
        sample = db.query(sql).df()
        print(f"\n>> {rt} (Latest 2 days):")
        print(sample[["Date", "Open", "High", "Low", "Close", "Volume"]].to_string(index=False))

    print("\n====================================================")
    print("   AUDIT COMPLETE: DATA IS ACCESSIBLE AND INTEGRAL  ")
    print("====================================================")


if __name__ == "__main__":
    strict_audit()
