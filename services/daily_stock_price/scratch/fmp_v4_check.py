from pathlib import Path

import requests


def test_v4_and_quotes():
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
        "v3/quote/AAPL",  # Standard Quote (Should be free)
        "v4/stock/list",  # Potential v4 version
        "v3/stock-publisher/list",  # Some docs mention this for v3
        "v3/symbol/NASDAQ",  # Retrying with a different format?
        "v3/available-traded/list",  # Retrying
        "v3/search?query=Apple",  # Simple search
    ]

    print(f"Testing key: {api_key[:4]}...{api_key[-4:]}")

    for ep in endpoints:
        symbol = "?" if "?" not in ep else "&"
        url = f"https://financialmodelingprep.com/api/{ep}{symbol}apikey={api_key}"

        try:
            print(f"\nTarget: {ep}")
            resp = requests.get(url)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    print(f"Count: {len(data)}")
                    if len(data) > 0:
                        print("Sample:", data[0])
                else:
                    print("Data:", str(data)[:100])
            else:
                print(f"Response: {resp.text[:150]}")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    test_v4_and_quotes()
