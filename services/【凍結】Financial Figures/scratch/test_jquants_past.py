import datetime
import pandas as pd
from src.engines.jp_engine import JPEngine
from loguru import logger
import sys
import os

def test_jquants_past():
    os.environ["PYTHONPATH"] = "."
    try:
        engine = JPEngine()
        # Test a date within subscription: 2026-02-01
        date_str = "20260201"
        print(f"Testing get_fin_summary for {date_str} (within sub window)...")
        
        try:
            # J-Quants V2 summary method
            df = engine.cli.get_fin_summary(date_yyyymmdd=date_str)
            print(f"get_fin_summary returned {len(df) if df is not None else 0} records")
            if df is not None and not df.empty:
                print("Columns:", df.columns.tolist())
                print("First row LocalCode:", df.iloc[0]["LocalCode"])
        except Exception as e:
            print(f"get_fin_summary failed: {e}")

    except Exception as e:
        print(f"Initialization failed: {e}")

if __name__ == "__main__":
    test_jquants_past()
