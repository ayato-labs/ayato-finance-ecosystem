import pytest
import pandas as pd
import os
import shutil
from pathlib import Path
from src.engine import IndexEngine
from src.schema import enforce_schema

@pytest.fixture
def temp_engine(tmp_path):
    """テスト用のテンポラリディレクトリを使用するエンジン"""
    db_dir = tmp_path / "test_data"
    return IndexEngine(base_dir=str(db_dir))

def test_engine_save_and_load(temp_engine):
    """データの保存と読み込みの基本フロー"""
    df = pd.DataFrame({
        "Date": [pd.Timestamp("2024-01-01")],
        "Open": [100.0], "High": [110.0], "Low": [90.0], "Close": [105.0], "Volume": [1000]
    })
    df = enforce_schema(df, "TEST", "src")
    
    temp_engine.save_data("TEST", df)
    prices = temp_engine.get_prices("TEST")
    
    assert len(prices) == 1
    assert prices[0]["Ticker"] == "TEST"

def test_engine_deduplication(temp_engine):
    """重複データの排除ロジック（厳しいテスト）"""
    # 1回目の保存
    df1 = pd.DataFrame({
        "Date": [pd.Timestamp("2024-01-01")],
        "Open": [100.0], "High": [110.0], "Low": [90.0], "Close": [100.0], "Volume": [1000]
    })
    df1 = enforce_schema(df1, "TEST", "src1")
    temp_engine.save_data("TEST", df1)
    
    # 2回目の保存（同じ日付だが価格が違う + Timestampが新しいはず）
    df2 = pd.DataFrame({
        "Date": [pd.Timestamp("2024-01-01")],
        "Open": [100.0], "High": [110.0], "Low": [90.0], "Close": [105.0], "Volume": [2000]
    })
    df2 = enforce_schema(df2, "TEST", "src2")
    temp_engine.save_data("TEST", df2)
    
    prices = temp_engine.get_prices("TEST")
    
    # 2件保存されているが、取得結果は1件だけであるべき
    assert len(prices) == 1
    # 最新の保存データ（Close=105.0）が優先されているべき
    assert prices[0]["Close"] == 105.0

def test_engine_special_ticker_naming(temp_engine):
    """^GSPCのような特殊文字を含むティッカーのファイル名処理"""
    ticker = "^GSPC"
    df = enforce_schema(pd.DataFrame({"Date":["2024-01-01"], "Close":[100]}), ticker, "src")
    temp_engine.save_data(ticker, df)
    
    expected_file = Path(temp_engine.base_dir) / "_GSPC.parquet"
    assert expected_file.exists()

def test_engine_non_existent_ticker(temp_engine):
    """存在しないデータを要求した場合の挙動"""
    prices = temp_engine.get_prices("NON_EXISTENT")
    assert prices == []
