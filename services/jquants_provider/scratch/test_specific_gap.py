import os
from jquantsapi import ClientV2
from src.core.config import settings

def test_specific_gap():
    cli = ClientV2(api_key=settings.JQUANTS_API_KEY)
    
    # Test the day Toyota stopped (Friday)
    d1 = "20240322"
    print(f"Testing API for {d1}...")
    try:
        df = cli.get_eq_bars_daily(date_yyyymmdd=d1)
        if df is not None and not df.empty:
            print(f"SUCCESS: Found {len(df)} records for {d1}")
            if "7203" in df["Code"].values:
                print("Toyota (7203) found in response.")
            else:
                print("Toyota (7203) NOT found in response.")
        else:
            print(f"FAILED: No data for {d1}")
    except Exception as e:
        print(f"ERROR: {e}")

    # Test the next Monday
    d2 = "20240325"
    print(f"\nTesting API for {d2}...")
    try:
        df = cli.get_eq_bars_daily(date_yyyymmdd=d2)
        if df is not None and not df.empty:
            print(f"SUCCESS: Found {len(df)} records for {d2}")
        else:
            print(f"FAILED: No data for {d2}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_specific_gap()
