import duckdb
from pathlib import Path

def check_earnings():
    db_path = Path("data/jquants_financials.duckdb")
    if not db_path.exists():
        print("Database not found.")
        return

    conn = duckdb.connect(str(db_path))
    query = """
    SELECT 
        COUNT(*) as total, 
        COUNT(NetSales) as with_sales 
    FROM company_facts 
    WHERE Type LIKE '%Earnings%'
    """
    res = conn.execute(query).fetchone()
    total = res[0]
    with_sales = res[1]
    
    print(f"--- Earnings Coverage Check ---")
    if total > 0:
        coverage = (with_sales / total) * 100
        print(f"Total 'Earnings' records: {total}")
        print(f"Records with NetSales: {with_sales}")
        print(f"Coverage: {coverage:.2f}%")
        
        if coverage > 95:
            print("Status: EXCELLENT - High data density for analysis.")
        elif coverage > 80:
            print("Status: GOOD - Most records are usable.")
        else:
            print("Status: WARN - Significant missing values even in Earnings reports.")
    else:
        print("No 'Earnings' type records found yet. Backfill is still in early stages.")
    
    conn.close()

if __name__ == "__main__":
    check_earnings()
