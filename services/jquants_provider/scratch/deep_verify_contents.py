import duckdb
import pandas as pd
from pathlib import Path

def deep_verify():
    prices_db = "data/jquants_prices.duckdb"
    master_db = "data/jquants_master.duckdb"
    facts_db = "data/jquants_financials.duckdb"

    # 1. Price Continuity Check (Toyota: 72030)
    print("--- [1] Price Continuity Check (72030: TOYOTA) ---")
    conn = duckdb.connect(prices_db)
    # Fetch price history
    query = """
    SELECT Date, Open, Close, AdjustmentClose, Volume 
    FROM daily_prices 
    WHERE Code = '72030' 
    ORDER BY Date ASC
    """
    df_prices = conn.execute(query).df()
    if not df_prices.empty:
        # Calculate daily return to find anomalies
        df_prices['Return'] = df_prices['Close'].pct_change()
        anomalies = df_prices[df_prices['Return'].abs() > 0.3] # 30% jump is rare
        print(f"Total trading days: {len(df_prices)}")
        print(f"Price Range: {df_prices['Close'].min()} to {df_prices['Close'].max()}")
        if not anomalies.empty:
            print("Potential anomalies (>30% change):")
            print(anomalies[['Date', 'Close', 'Return']])
        else:
            print("No extreme price jumps detected (>30%). Adjustments seem consistent.")
    else:
        print("No price data found for 72030.")
    conn.close()

    # 2. Financial Consistency Check (Multiple Quarters)
    print("\n--- [2] Financial Consistency Check (72030: TOYOTA) ---")
    if Path(facts_db).exists():
        conn = duckdb.connect(facts_db)
        query = """
        SELECT DisclosedDate, FiscalPeriod, NetSales, OperatingProfit 
        FROM company_facts 
        WHERE LocalCode = '72030' AND Type LIKE '%Earnings%'
        ORDER BY DisclosedDate ASC
        """
        df_facts = conn.execute(query).df()
        if not df_facts.empty:
            print("Fiscal progression for 72030:")
            print(df_facts.to_string(index=False))
        else:
            print("No financial data found for 72030 (Backfill might be in progress).")
        conn.close()

    # 3. Cross-Table Relational Integrity
    print("\n--- [3] Relational Integrity (5-digit Join) ---")
    conn = duckdb.connect(master_db)
    # Attach prices DB to perform join
    conn.execute(f"ATTACH '{prices_db}' AS prices_db")
    query = """
    SELECT 
        p.Code, 
        m.name as CompanyName, 
        p.Date, 
        p.Close
    FROM prices_db.daily_prices p
    JOIN tickers m ON p.Code = m.code
    WHERE p.Date = '2026-02-10'
    LIMIT 5
    """
    try:
        df_join = conn.execute(query).df()
        print("Joined Sample Data (Prices + Master):")
        print(df_join.to_string(index=False))
    except Exception as e:
        print(f"Join failed: {e}")
    conn.close()

if __name__ == "__main__":
    deep_verify()
