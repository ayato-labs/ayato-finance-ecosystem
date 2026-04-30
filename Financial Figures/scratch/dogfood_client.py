import json

import httpx

BASE_URL = "http://localhost:5005"


def test_api():
    print("=== Dogfooding: Financial API Server ===")

    # 1. Health Check
    print("\n1. Checking Health...")
    try:
        res = httpx.get(f"{BASE_URL}/health")
        print(f"Status: {res.status_code}")
    except Exception as e:
        print(f"Error connecting to server: {e}")
        return

    # 2. Get Stats
    print("\n2. Checking DB Statistics...")
    stats = httpx.get(f"{BASE_URL}/stats").json()
    print(f"US Facts: {stats.get('us_facts', 0)}")

    # 3. List US Tickers
    print("\n3. Listing Tickers (market=US)...")
    tickers = httpx.get(f"{BASE_URL}/tickers?market=US&limit=5").json()
    if not tickers:
        print("No US tickers found.")
        return

    # We'll use symbols that we KNOW exist in the data we just synced or previous tests
    # Let's try to find 'AAPL' or 'A' or any ticker that actually has facts
    print("\n4. Searching for a ticker with facts...")
    target_symbol = None
    for t in tickers:
        sym = t["symbol"]
        f_check = httpx.get(f"{BASE_URL}/financials/{sym}?limit=1").json()
        if isinstance(f_check, list) and len(f_check) > 0:
            target_symbol = sym
            print(f"Found data for {sym}!")
            break

    if not target_symbol:
        print(
            "Could not find any ticker with financial records in the first 5. Checking all US stats..."
        )
        # Fallback to the first one just to see the error/response
        target_symbol = tickers[0]["symbol"]

    # 5. Fetch Full Financials
    print(f"\n5. Fetching Standardized Financials for {target_symbol}...")
    res = httpx.get(f"{BASE_URL}/financials/{target_symbol}?limit=10")
    print(f"API Response Status: {res.status_code}")

    financials = res.json()

    if isinstance(financials, list):
        print(f"Received list with {len(financials)} records.")
        for record in financials[:3]:
            print(f"--- {record.get('target_label', 'Unknown')} ---")
            print(f"  Value: {record.get('value')} {record.get('unit')}")
            print(f"  Date:  {record.get('period_date')} (FY{record.get('fiscal_year')})")
            print(f"  AI Reasoning: {record.get('reasoning')}")
    else:
        print("Expected a list from /financials but got:")
        print(json.dumps(financials, indent=2))


if __name__ == "__main__":
    test_api()
