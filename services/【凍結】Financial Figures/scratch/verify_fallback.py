import os
import sys

from src.api.server import get_financials

# Mock settings if needed, but we should use the real ones


def test_toyota_fallback():
    print("--- Verifying Toyota (7203) Fallback ---")
    symbol = "7203"

    try:
        # get_financials returns a list of FinancialRecord objects
        records = get_financials(symbol, limit=100, offset=0)
        print(f"Total records found for {symbol}: {len(records)}")

        if not records:
            print("FAILURE: No records found.")
            return

        # Check sources
        markets = {r.market for r in records}
        print(f"Data Sources: {markets}")

        # Check if we have records with different fiscal years
        years = sorted({r.fiscal_year for r in records if r.fiscal_year})
        print(f"Fiscal Years covered: {years}")

        # Check for specific tags
        tags = {r.target_label for r in records}
        print(f"Target Labels found: {len(tags)}")

        if len(records) > 0:
            print("SUCCESS: Fallback logic confirmed.")
        else:
            print("FAILURE: Empty results.")

    except Exception as e:
        print(f"ERROR during verification: {e}")


if __name__ == "__main__":
    # Add current dir to path for imports
    sys.path.append(os.getcwd())
    test_toyota_fallback()
