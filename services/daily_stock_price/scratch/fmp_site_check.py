import requests
from pathlib import Path

def test_site_subdomain():
    env_path = Path(__file__).parent.parent / ".env"
    api_key = None
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                if line.startswith("FMP_API_KEY="):
                    api_key = line.split("=")[1].strip()
                    break

    if not api_key:
        print("Error: FMP_API_KEY not found in .env")
        return

    # Modern FMP endpoints often use 'site.' subdomain in some regions/versions
    bases = [
        "https://financialmodelingprep.com/api",
        "https://site.financialmodelingprep.com/api"
    ]
    
    # v3 vs v4
    endpoints = [
        "v3/stock/list",
        "v3/symbol/available-traded", # Different variation
        "v4/stock-symbol",
        "v3/quote/AAPL"
    ]

    print(f"Testing key: {api_key[:4]}...{api_key[-4:]}")

    for base in bases:
        for ep in endpoints:
            url = f"{base}/{ep}?apikey={api_key}"
            try:
                print(f"\nTarget: {url.replace(api_key, 'SECRET')}")
                resp = requests.get(url)
                print(f"Status: {resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json()
                    print(f"Count: {len(data)}")
                    if len(data) > 0: print("Sample:", data[0])
                else:
                    print(f"Response: {resp.text[:100]}")
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    test_site_subdomain()
