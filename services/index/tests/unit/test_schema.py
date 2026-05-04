import numpy as np
import pandas as pd

from src.schema import COLUMNS, enforce_schema


def test_enforce_schema_normal():
    """正常なデータが正しく処理されるか"""
    df = pd.DataFrame(
        {
            "Date": ["2024-01-01"],
            "Open": [100.0],
            "High": [110.0],
            "Low": [90.0],
            "Close": [105.0],
            "Volume": [1000],
        }
    )
    result = enforce_schema(df, "^GSPC", "test_source")

    assert len(result) == 1
    assert list(result.columns) == COLUMNS
    assert result["Ticker"][0] == "^GSPC"
    assert result["Source"][0] == "test_source"
    assert isinstance(result["Date"][0], pd.Timestamp)


def test_enforce_schema_missing_columns():
    """カラムが欠損している場合に補完されるか(厳しいテスト)"""
    df = pd.DataFrame(
        {
            "Date": ["2024-01-01"],
            "Close": [105.0],
            # Open, High, Low, Volume がない
        }
    )
    result = enforce_schema(df, "^GSPC", "test_source")

    assert "Open" in result.columns
    assert np.isnan(result["Open"][0])
    assert result["Volume"][0] == 0


def test_enforce_schema_invalid_types():
    """不正なデータ型が強制的に変換されるか(厳しいテスト)"""
    df = pd.DataFrame(
        {
            "Date": ["2024-01-01"],
            "Open": ["invalid"],  # 文字列が混入
            "High": [110.0],
            "Low": [90.0],
            "Close": [105.0],
            "Volume": ["1000"],  # 文字列の数字
        }
    )
    result = enforce_schema(df, "^GSPC", "test_source")

    assert np.isnan(result["Open"][0])  # invalidはNaNになるはず
    assert result["Volume"][0] == 1000
    assert result["Volume"].dtype == np.int64


def test_enforce_schema_empty():
    """空のデータフレームが入力された場合の挙動"""
    df = pd.DataFrame()
    result = enforce_schema(df, "^GSPC", "test_source")
    assert len(result) == 0
    assert list(result.columns) == COLUMNS
