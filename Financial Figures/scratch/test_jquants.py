import os
import sys

import jquantsapi
from dotenv import load_dotenv

# Add current directory to path
sys.path.append(os.getcwd())


def test_connection():
    load_dotenv()
    api_key = os.getenv("JQUANTS_API_KEY")
    refresh_token = os.getenv("JQUANTS_REFRESH_TOKEN")

    print("--- J-Quants Connectivity Test ---")
    print(f"API Key: {api_key[:5]}...{api_key[-5:] if api_key else 'None'}")

    try:
        if refresh_token:
            print("Using V1 Refresh Token...")
            cli = jquantsapi.Client(refresh_token=refresh_token)
        elif api_key:
            print("Using V2 API Key...")
            cli = jquantsapi.ClientV2(api_key=api_key)
        else:
            print("ERROR: No credentials found in .env")
            return

        print("Attempting to fetch ticker list (equities/master)...")
        tickers = cli.get_list()
        print(f"SUCCESS: Fetched {len(tickers)} tickers.")

        print("\nAttempting to fetch a sample financial summary (code=7203)...")
        fin = cli.get_statements(code="7203")
        print(f"SUCCESS: Fetched {len(fin)} records for Toyota (7203).")

        print("\nConclusion: J-Quants API is ALIVE and responding correctly.")

    except Exception as e:
        print("\nFAILURE: API call failed.")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {e!s}")

        if "429" in str(e):
            print("\nAnalysis: The API is alive, but you have hit the RATE LIMIT.")
        elif "401" in str(e) or "403" in str(e):
            print("\nAnalysis: Authentication or Subscription issue.")
        else:
            print("\nAnalysis: Unexpected error. Check network or API status.")


if __name__ == "__main__":
    test_connection()
