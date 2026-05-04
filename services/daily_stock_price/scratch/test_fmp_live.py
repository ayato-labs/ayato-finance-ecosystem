import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from src.universe import UniverseManager


def test_live_fmp():
    # Attempt to read API KEY from .env manually
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

    print(f"Using API Key: {api_key[:4]}...{api_key[-4:]}")

    # Initialize UniverseManager with the real key
    um = UniverseManager(fmp_api_key=api_key)

    # Force refresh by removing existing cache if any
    cache_file = Path("./data/universe/us_tickers_full.csv")
    if cache_file.exists():
        os.remove(cache_file)
        print("Cleared existing US ticker cache for fresh test.")

    # Execute discovery
    print("Fetching US tickers from FMP (Live)...")
    tickers = um.get_us_universe()

    print("\n--- Live Verification Results ---")
    print(f"Total US Tickers Discovered: {len(tickers)}")

    if len(tickers) > 0:
        print("Samples (First 10):", tickers[:10])
        print(f"Cache file created: {cache_file.absolute()}")

        # Verify it's more than just S&P 500
        if len(tickers) > 1000:
            print("Status: ✅ SUCCESS - Coverage is significantly larger than S&P 500.")
        else:
            print("Status: ⚠️ WARNING - Coverage count is lower than expected for full market.")
    else:
        print("Status: ❌ FAILED - No tickers retrieved. Check API key and network.")


if __name__ == "__main__":
    test_live_fmp()
