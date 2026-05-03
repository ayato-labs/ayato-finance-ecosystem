import pandas as pd
import requests

API_BASE = "http://127.0.0.1:5006"


def test_extraction(symbol):
    print(f"\n>>> Requesting data for {symbol} from API...")
    try:
        url = f"{API_BASE}/financials/{symbol}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if not data:
            print(f"No standardized data found for {symbol}")
            return

        df = pd.DataFrame(data)
        # Select key labels for the showcase
        important_labels = ["NetSales", "OperatingProfit", "NetProfit", "EPS", "Equity"]
        df_show = df[df["target_label"].isin(important_labels)].copy()

        # Sort by date descending
        df_show = df_show.sort_values(["period_date", "target_label"], ascending=[False, True])

        print(f"--- Standardized Results for {symbol} ({len(data)} items) ---")
        print(
            df_show[["period_date", "target_label", "value", "unit"]]
            .head(15)
            .to_string(index=False)
        )

    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")


if __name__ == "__main__":
    # Test for both targets
    test_extraction("TSLA")
    test_extraction("7203")
