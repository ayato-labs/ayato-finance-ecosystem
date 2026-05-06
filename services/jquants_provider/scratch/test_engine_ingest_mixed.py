import pandas as pd
from decimal import Decimal
from src.core.db import db_manager
from src.core.config import settings
from src.engine import JPEngine

def test_ingestion_mixed():
    engine = JPEngine()
    
    # Mix of small values, None, and large value
    data = []
    # Add 100 small values to trick DuckDB inference
    for i in range(100):
        data.append({
            "Date": "2026-05-06",
            "Code": f"{1000+i}",
            "Open": Decimal("100.0"),
            "High": Decimal("100.0"),
            "Low": Decimal("100.0"),
            "Close": Decimal("100.0"),
            "Volume": 1000,
            "AdjustmentOpen": Decimal("100.0"),
            "AdjustmentHigh": Decimal("100.0"),
            "AdjustmentLow": Decimal("100.0"),
            "AdjustmentClose": Decimal("100.0"),
            "AdjustmentVolume": 1000,
            "TurnoverValue": Decimal("100.0"), # Small decimal
        })
        
    data.append({
        "Date": "2026-05-06",
        "Code": "9999",
        "Open": Decimal("100.0"),
        "High": Decimal("100.0"),
        "Low": Decimal("100.0"),
        "Close": Decimal("100.0"),
        "Volume": 1000,
        "AdjustmentOpen": Decimal("100.0"),
        "AdjustmentHigh": Decimal("100.0"),
        "AdjustmentLow": Decimal("100.0"),
        "AdjustmentClose": Decimal("100.0"),
        "AdjustmentVolume": 1000,
        "TurnoverValue": Decimal("158609607470.0"), # HUGE decimal
    })
    
    df = pd.DataFrame(data)
    
    print("Ingesting mixed data...")
    try:
        engine.ingest_prices(df, session_id="test2")
        print("Success!")
    except Exception as e:
        print(f"Ingestion failed: {e}")

if __name__ == "__main__":
    test_ingestion_mixed()
