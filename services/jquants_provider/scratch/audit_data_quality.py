import duckdb
import pandas as pd
from pathlib import Path
from loguru import logger

def audit_data():
    data_dir = Path("data")
    prices_db = data_dir / "jquants_prices.duckdb"
    master_db = data_dir / "jquants_master.duckdb"
    facts_db = data_dir / "jquants_financials.duckdb"

    results = []

    # 1. Master Data Audit
    if master_db.exists():
        conn = duckdb.connect(str(master_db))
        ticker_count = conn.execute("SELECT COUNT(*) FROM tickers").fetchone()[0]
        invalid_codes = conn.execute("SELECT COUNT(*) FROM tickers WHERE length(code) != 5").fetchone()[0]
        unmapped_sectors = conn.execute("SELECT COUNT(*) FROM tickers WHERE sector_id IS NULL OR sector_id = 0").fetchone()[0]
        
        results.append({
            "Category": "Master",
            "Metric": "Total Tickers",
            "Value": ticker_count,
            "Status": "OK" if ticker_count > 4000 else "WARN"
        })
        results.append({
            "Category": "Master",
            "Metric": "Invalid Codes (non-5 digit)",
            "Value": invalid_codes,
            "Status": "OK" if invalid_codes == 0 else "FAIL"
        })
        conn.close()

    # 2. Price Data Audit
    if prices_db.exists():
        conn = duckdb.connect(str(prices_db))
        price_count = conn.execute("SELECT COUNT(*) FROM daily_prices").fetchone()[0]
        date_range = conn.execute("SELECT MIN(Date), MAX(Date) FROM daily_prices").fetchone()
        distinct_tickers = conn.execute("SELECT COUNT(DISTINCT Code) FROM daily_prices").fetchone()[0]
        
        # Check for Nulls in critical columns
        null_prices = conn.execute("SELECT COUNT(*) FROM daily_prices WHERE Close IS NULL OR Volume IS NULL").fetchone()[0]
        
        results.append({
            "Category": "Prices",
            "Metric": "Total Records",
            "Value": price_count,
            "Status": "OK"
        })
        results.append({
            "Category": "Prices",
            "Metric": "Active Tickers in Price DB",
            "Value": distinct_tickers,
            "Status": "OK" if distinct_tickers > 3500 else "WARN"
        })
        results.append({
            "Category": "Prices",
            "Metric": "Latest Date",
            "Value": str(date_range[1]),
            "Status": "INFO"
        })
        results.append({
            "Category": "Prices",
            "Metric": "Null Prices/Volume",
            "Value": null_prices,
            "Status": "OK" if null_prices == 0 else "FAIL"
        })
        conn.close()

    # 3. Financial Data Audit
    if facts_db.exists():
        conn = duckdb.connect(str(facts_db))
        fact_count = conn.execute("SELECT COUNT(*) FROM company_facts").fetchone()[0]
        
        if fact_count > 0:
            null_sales = conn.execute("SELECT COUNT(*) FROM company_facts WHERE NetSales IS NULL").fetchone()[0]
            null_profit = conn.execute("SELECT COUNT(*) FROM company_facts WHERE OperatingProfit IS NULL").fetchone()[0]
            
            results.append({
                "Category": "Financials",
                "Metric": "Total Fact Records",
                "Value": fact_count,
                "Status": "OK"
            })
            results.append({
                "Category": "Financials",
                "Metric": "Null NetSales Rate",
                "Value": f"{(null_sales/fact_count)*100:.2f}%",
                "Status": "OK" if (null_sales/fact_count) < 0.1 else "WARN"
            })
        else:
            results.append({
                "Category": "Financials",
                "Metric": "Total Fact Records",
                "Value": 0,
                "Status": "FAIL (Empty)"
            })
        conn.close()

    df_results = pd.DataFrame(results)
    print("\n=== DATA QUALITY AUDIT REPORT ===")
    print(df_results.to_string(index=False))
    
    if fact_count == 0:
        print("\n[CRITICAL] Financial data is missing. Need to re-run sync-market.")

if __name__ == "__main__":
    audit_data()
