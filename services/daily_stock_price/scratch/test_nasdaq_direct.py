import requests
import io
import pandas as pd

def test_nasdaq_download():
    # URL for Nasdaq listed stocks (official)
    url = "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        print(f"Downloading from: {url}")
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        # It's pipe delimited |
        data = io.StringIO(resp.text)
        df = pd.read_csv(data, sep="|")
        
        print(f"Success! Found {len(df)} tickers.")
        print("Sample:", df["Symbol"].head().tolist())
        
        # Check 'Other' listed (NYSE/AMEX)
        url_other = "https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt"
        resp_other = requests.get(url_other, headers=headers, timeout=10)
        df_other = pd.read_csv(io.StringIO(resp_other.text), sep="|")
        print(f"Success (Other)! Found {len(df_other)} tickers.")
        
    except Exception as e:
        print(f"Failed to download from NasdaqTrader: {e}")

if __name__ == "__main__":
    test_nasdaq_download()
