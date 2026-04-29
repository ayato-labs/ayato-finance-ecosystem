import os

import httpx
from dotenv import load_dotenv


def test_v2():
    load_dotenv()
    api_key = os.getenv("JQUANTS_API_KEY")
    if not api_key:
        print("Error: JQUANTS_API_KEY not found in .env")
        return

    headers = {"x-api-key": api_key}

    # Test 1: Listed Info (Commonly used)
    url_listed = "https://api.jquants.com/v2/listed/info"
    print(f"Testing {url_listed}...")
    try:
        r = httpx.get(url_listed, headers=headers)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")

    # Test 2: Financial Statements for JPX (8697)
    url_fins = "https://api.jquants.com/v2/fins/statements"
    params = {"code": "8697"}
    print(f"\nTesting {url_fins}...")
    try:
        r = httpx.get(url_fins, headers=headers, params=params)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    test_v2()
