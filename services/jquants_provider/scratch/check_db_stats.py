import duckdb
from pathlib import Path
import pandas as pd

db_path = Path("data/jquants.duckdb")

def check_data_integrity():
    if not db_path.exists():
        print("Database not found.")
        return

    conn = duckdb.connect(str(db_path))
    
    print("=== Database Statistics ===")
    
    # 1. Tickers
    ticker_count = conn.execute("SELECT count(*) FROM tickers").fetchone()[0]
    print(f"Tickers: {ticker_count} records")
    if ticker_count > 0:
        print("\nSample Tickers (First 3):")
        print(conn.execute("SELECT code, name, market_section_id FROM tickers LIMIT 3").df())

    # 2. Daily Prices
    try:
        price_count = conn.execute("SELECT count(*) FROM daily_prices").fetchone()[0]
        if price_count > 0:
            stats = conn.execute("SELECT MIN(Date), MAX(Date), COUNT(DISTINCT Code) FROM daily_prices").fetchone()
            print(f"\nDaily Prices: {price_count} records")
            print(f"  Range: {stats[0]} to {stats[1]}")
            print(f"  Unique Stocks: {stats[2]}")
            print("\nSample Prices (Latest 3):")
            print(conn.execute("SELECT Code, Date, Close, Volume FROM daily_prices ORDER BY Date DESC, Code LIMIT 3").df())
        else:
            print("\nDaily Prices: 0 records")
    except Exception as e:
        print(f"\nDaily Prices check failed: {e}")

    # 3. Financial Summaries (Facts)
    try:
        fact_count = conn.execute("SELECT count(*) FROM company_facts").fetchone()[0]
        if fact_count > 0:
            print(f"\nFinancial Facts: {fact_count} records")
            print("\nSample Facts (Latest 3):")
            print(conn.execute("SELECT Code, DisclosedDate, NetSales, OrdinaryProfit FROM company_facts ORDER BY DisclosedDate DESC LIMIT 3").df())
        else:
            print("\nFinancial Facts: 0 records")
    except Exception as e:
        print(f"\nFinancial Facts check failed: {e}")

    conn.close()

if __name__ == "__main__":
    check_data_integrity()
