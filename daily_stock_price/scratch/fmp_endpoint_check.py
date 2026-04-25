import requests
from pathlib import Path

def test_endpoints():
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

    endpoints = [
        "v3/stock/list",
        "v3/available-traded/list",
        "v3/symbol/NASDAQ",
        "v3/search?query=AA" # Basic search to verify key is good
    ]

    print(f"Testing key: {api_key[:4]}...{api_key[-4:]}")

    for ep in endpoints:
        url = f"https://financialmodelingprep.com/api/{ep}&apikey={api_key}"
        # Fix URL formatting (some might need ? or & depending on if they have params)
        if "?" not in ep:
            url = f"https://financialmodelingprep.com/api/{ep}?apikey={api_key}"
        else:
            url = f"https://financialmodelingprep.com/api/{ep}&apikey={api_key}"

        try:
            print(f"\nTarget: {ep}")
            resp = requests.get(url)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"Count: {len(data)}")
                if isinstance(data, list) and len(data) > 0:
                    print("Sample:", data[0])
            else:
                print(f"Response: {resp.text[:100]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_endpoints()
