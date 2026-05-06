import os
from jquantsapi import ClientV2
from src.core.config import settings

def test_api_range():
    cli = ClientV2(
        api_key=settings.JQUANTS_API_KEY
    )
    
    # Test a recent date
    test_date = "20260501"
    print(f"Testing API for {test_date}...")
    try:
        # Correct method for ClientV2 is get_eq_bars_daily
        df = cli.get_eq_bars_daily(date_yyyymmdd=test_date)
        if df is not None and not df.empty:
            print(f"SUCCESS: Found {len(df)} records for {test_date}")
        else:
            print(f"FAILED: No data for {test_date}")
    except Exception as e:
        print(f"ERROR: {e}")

    # Test an old date (e.g. 6 months ago)
    old_date = "20251101"
    print(f"\nTesting API for {old_date}...")
    try:
        df = cli.get_eq_bars_daily(date_yyyymmdd=old_date)
        if df is not None and not df.empty:
            print(f"SUCCESS: Found {len(df)} records for {old_date}")
        else:
            print(f"FAILED: No data for {old_date}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_api_range()
