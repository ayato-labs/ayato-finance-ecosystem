import pandas as pd
from decimal import Decimal
from src.core.db import db_manager
from src.core.config import settings
from src.engine import JPEngine

def test_ingestion():
    engine = JPEngine()
    
    # Fake large record
    data = [{
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
        "TurnoverValue": Decimal("158609607470.0"),
    }]
    
    df = pd.DataFrame(data)
    
    print(f"Connecting to: {settings.JP_PRICES_DB_PATH}")
    with db_manager.connect(settings.JP_PRICES_DB_PATH) as conn:
        schema = conn.execute("DESCRIBE daily_prices").fetchall()
        for col in schema:
            if col[0] == 'TurnoverValue':
                print(f"Schema TurnoverValue: {col[1]}")
                
    print("Ingesting...")
    try:
        engine.ingest_prices(df, session_id="test")
        print("Success!")
    except Exception as e:
        print(f"Ingestion failed: {e}")

if __name__ == "__main__":
    test_ingestion()
