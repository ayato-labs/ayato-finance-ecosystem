from decimal import Decimal
from datetime import date
from src.core.contracts import JPFactContract
import math

def test_nan_validation():
    data = {
        "DisclosedDate": "2024-02-20",
        "DisclosedTime": "15:00:00",
        "LocalCode": "1301",
        "DisclosureNumber": "20240220540000",
        "Type": "Q1",
        "FiscalYear": "2024",
        "FiscalPeriod": "Q1",
        "NetSales": float('nan'),
        "OperatingProfit": 1000.5,
        "OrdinaryProfit": "－", # This won't be NaN yet unless we simulate engine preprocessing
        "Profit": None,
        "session_id": "test-session"
    }
    
    # Simulate engine's pd.to_numeric(..., errors="coerce")
    processed_data = data.copy()
    processed_data["NetSales"] = float('nan')
    # OrdinaryProfit is "－" in raw, but engine makes it NaN
    processed_data["OrdinaryProfit"] = float('nan')
    
    contract = JPFactContract(**processed_data)
    print(f"Validated NetSales: {contract.NetSales}")
    print(f"Validated OrdinaryProfit: {contract.OrdinaryProfit}")
    assert contract.NetSales is None
    assert contract.OrdinaryProfit is None
    assert contract.OperatingProfit == Decimal("1000.5")
    print("Success: NaN validation handled correctly.")

if __name__ == "__main__":
    try:
        test_nan_validation()
    except Exception as e:
        print(f"Validation failed: {e}")
