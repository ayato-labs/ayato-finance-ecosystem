import datetime
import pandas as pd
from src.engines.jp_engine import JPEngine
from loguru import logger
import sys

def test_jquants():
    try:
        engine = JPEngine()
        # Try to fetch listed companies first to verify connectivity
        # tickers = engine.cli.get_list()
        # print(f"Tickers found: {len(tickers)}")
        
        # Test get_fin_summary for a recent weekday
        test_date = datetime.date.today() - datetime.timedelta(days=3) # Friday if today is Monday
        date_str = test_date.strftime("%Y%m%d")
        print(f"Testing get_fin_summary for {date_str}...")
        
        try:
            df = engine.cli.get_statements(date=date_str) # V2 often uses get_statements
            print(f"get_statements returned {len(df) if df is not None else 0} records")
            if df is not None and not df.empty:
                print("Columns:", df.columns.tolist())
        except Exception as e:
            print(f"get_statements failed: {e}")

        try:
            df = engine.cli.get_fin_summary(date_yyyymmdd=date_str)
            print(f"get_fin_summary returned {len(df) if df is not None else 0} records")
            if df is not None and not df.empty:
                print("Columns:", df.columns.tolist())
        except Exception as e:
            print(f"get_fin_summary failed: {e}")

    except Exception as e:
        print(f"Initialization failed: {e}")

if __name__ == "__main__":
    test_jquants()
