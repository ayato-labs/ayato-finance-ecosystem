import sys
import os
sys.path.append(os.getcwd())
from src.api.server import get_financials

def verify(symbol):
    print(f"--- Verifying {symbol} ---")
    try:
        records = get_financials(symbol, limit=50, offset=0)
        print(f"Total: {len(records)}")
        if records:
            print(f"Example: {records[0].target_label} | {records[0].value} | {records[0].period_date}")
            # Check if any have Unknown Company (meaning they came purely from EDINET without JP ticker match)
            unknowns = [r for r in records if r.market == "JP" and "Unknown" in r.market] # Wait, market is "JP"
            # In server.py: r.market = "JP" hardcoded for is_jp
            # But company_name is "Unknown Company" if no JP ticker found
            print(f"Company: {records[0].market}") # Wait, FinancialRecord doesn't have company_name, it has market
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify("7203") # Toyota (JP)
    verify("5889") # Only EDINET (likely)
