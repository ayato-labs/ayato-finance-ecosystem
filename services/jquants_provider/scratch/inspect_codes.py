import os
from jquantsapi import ClientV2
from src.core.config import settings

def inspect_codes():
    cli = ClientV2(api_key=settings.JQUANTS_API_KEY)
    df = cli.get_eq_bars_daily(date_yyyymmdd="20240322")
    if df is not None and not df.empty:
        print(f"Total columns: {df.columns.tolist()}")
        print(f"Sample codes: {df['Code'].head(10).tolist()}")
        # Check for anything starting with 7203
        toyota_match = [c for c in df['Code'].astype(str) if c.startswith('7203')]
        print(f"Matches for '7203': {toyota_match}")
    else:
        print("No data.")

if __name__ == "__main__":
    inspect_codes()
