import duckdb
from pathlib import Path

def inspect():
    # 1. Price Check
    p_db = "data/jquants_prices.duckdb"
    conn = duckdb.connect(p_db)
    print("=== TOYOTA (72030) PRICE SAMPLE ===")
    res = conn.execute("SELECT Date, Close, AdjustmentClose, Volume FROM daily_prices WHERE Code = '72030' ORDER BY Date DESC LIMIT 10").fetchall()
    for row in res:
        print(row)
    conn.close()

    # 2. Financial Check
    f_db = "data/jquants_financials.duckdb"
    if Path(f_db).exists():
        conn = duckdb.connect(f_db)
        print("\n=== TOYOTA (72030) FINANCIAL SAMPLE ===")
        res = conn.execute("SELECT DisclosedDate, FiscalPeriod, NetSales, OperatingProfit FROM company_facts WHERE LocalCode = '72030' ORDER BY DisclosedDate DESC LIMIT 5").fetchall()
        for row in res:
            print(row)
        conn.close()

if __name__ == "__main__":
    inspect()
