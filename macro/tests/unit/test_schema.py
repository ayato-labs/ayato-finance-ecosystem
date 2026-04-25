import pytest
import pandas as pd
import numpy as np
from src.schema import enforce_schema, COLUMNS

def test_enforce_schema_from_series():
    """FREDのSeriesデータが正しく正規化されるか"""
    series = pd.Series([5.25, 5.50], index=pd.to_datetime(["2024-01-01", "2024-02-01"]), name="Value")
    result = enforce_schema(series, "FEDFUNDS", "fred")
    
    assert len(result) == 2
    assert list(result.columns) == COLUMNS
    assert result["Symbol"][0] == "FEDFUNDS"
    assert result["Value"][0] == 5.25
    assert result["Source"][0] == "fred"

def test_enforce_schema_invalid_value():
    """不正な数値（文字列など）がNaNに変換されるか（厳しいテスト）"""
    df = pd.DataFrame({
        "Date": ["2024-01-01"],
        "Value": ["invalid_rate"]
    })
    result = enforce_schema(df, "DFF", "fred")
    
    assert np.isnan(result["Value"][0])
    assert result["Value"].dtype == np.float64

def test_enforce_schema_date_normalization():
    """日付が正規化（時刻除去）されるか"""
    df = pd.DataFrame({
        "Date": [pd.Timestamp("2024-01-01 15:30:00")],
        "Value": [1.23]
    })
    result = enforce_schema(df, "TEST", "src")
    assert result["Date"][0] == pd.Timestamp("2024-01-01")
