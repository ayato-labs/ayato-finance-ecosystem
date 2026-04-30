from pathlib import Path

import duckdb

# DB Path configuration
base_dir = Path("./data/market_data")
parquet_pattern = base_dir / "**/*.parquet"


def verify_data():
    db = duckdb.connect()

    print("\n--- [System Verification: Data Integrity Check] ---")

    # 1. Check total record count and unique tickers in the requested period
    print("\n1. Summary for Period 2026-03-15 to 2026-04-15:")
    query_summary = f"""
    SELECT
        COUNT(*) as total_records,
        COUNT(DISTINCT Ticker) as unique_tickers,
        MIN(Date) as min_date,
        MAX(Date) as max_date
    FROM read_parquet('{parquet_pattern}')
    WHERE Date >= '2026-03-15' AND Date <= '2026-04-15'
    """
    res = db.execute(query_summary).df()
    print(res.to_string(index=False))

    # 2. Check specific tickers (US & JP)
    test_tickers = ["AAPL", "MSFT", "1301.T", "1332.T"]
    print(f"\n2. Detailed Check for Samples: {test_tickers}")

    # We use the View logic to get the 'latest' truth
    for ticker in test_tickers:
        query_ticker = f"""
        SELECT
            Ticker,
            MIN(Date) as start,
            MAX(Date) as end,
            COUNT(*) as count,
            AVG(Close) as avg_price
        FROM (
            SELECT *,
                   row_number() OVER (PARTITION BY Date ORDER BY LoadTimestamp DESC) as row_num
            FROM read_parquet('{parquet_pattern}')
            WHERE Ticker = '{ticker}' AND Date >= '2026-03-15'
        )
        WHERE row_num = 1
        GROUP BY Ticker
        """
        res_ticker = db.execute(query_ticker).df()
        if not res_ticker.empty:
            print(
                f"  [PASS] {ticker}: {res_ticker['count'].iloc[0]} records from {res_ticker['start'].iloc[0]} to {res_ticker['end'].iloc[0]}"
            )
        else:
            print(f"  [FAIL] {ticker}: No data found in the specified range.")

    # 3. Check for obvious data issues (Nulls in price)
    print("\n3. Quality Check (Null values in Open/Close/Volume):")
    query_quality = f"""
    SELECT
        COUNT(*) as null_count
    FROM read_parquet('{parquet_pattern}')
    WHERE Date >= '2026-03-15'
      AND (Open IS NULL OR Close IS NULL)
    """
    null_res = db.execute(query_quality).fetchone()[0]
    if null_res == 0:
        print("  [PASS] No NULL values found in price columns.")
    else:
        print(f"  [WARNING] {null_res} records have NULL values.")
        # Investigation
        sample_nulls = f"""
        SELECT Ticker, Date, Source
        FROM read_parquet('{parquet_pattern}')
        WHERE Date >= '2026-03-15' AND (Open IS NULL OR Close IS NULL)
        LIMIT 5
        """
        print("  Sample tickers with NULLs:")
        print(db.execute(sample_nulls).df().to_string(index=False))


if __name__ == "__main__":
    verify_data()
