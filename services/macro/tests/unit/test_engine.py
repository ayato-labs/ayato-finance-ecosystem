import pytest
import pandas as pd
from pathlib import Path
from src.engine import MacroEngine
from src.schema import enforce_schema

@pytest.fixture
def temp_engine(tmp_path):
    return MacroEngine(base_dir=str(tmp_path / "macro_test"))

def test_engine_save_and_latest_date(temp_engine):
    """保存と最新日付取得の検証"""
    symbol = "DFF"
    df = pd.DataFrame({"Date": ["2024-01-01"], "Value": [5.25]})
    df = enforce_schema(df, symbol, "fred")
    
    temp_engine.save_data(symbol, df)
    assert temp_engine.get_latest_date(symbol) == pd.Timestamp("2024-01-01")

def test_engine_deduplication_latest_wins(temp_engine):
    """重複した日付の場合、最新のLoadTimestampが勝つか(厳しいテスト)"""
    symbol = "DGS10"
    # 1回目の取得(古い)
    df1 = enforce_schema(pd.DataFrame({"Date": ["2024-01-01"], "Value": [4.0]}), symbol, "fred")
    temp_engine.save_data(symbol, df1)
    
    # 2回目の取得(新しい修正値)
    df2 = enforce_schema(pd.DataFrame({"Date": ["2024-01-01"], "Value": [4.1]}), symbol, "fred")
    temp_engine.save_data(symbol, df2)
    
    values = temp_engine.get_values(symbol)
    assert len(values) == 1
    assert values[0]["Value"] == 4.1 # 新しい方の値が採用されていること

def test_engine_filename_sanitization(temp_engine):
    """ファイル名に使えない文字の置換"""
    symbol = "FED/FUNDS.RATE"
    df = enforce_schema(pd.DataFrame({"Date": ["2024-01-01"], "Value": [5.0]}), symbol, "src")
    temp_engine.save_data(symbol, df)
    
    # スラッシュやドットがアンダースコアに置換されているか
    expected_file = Path(temp_engine.base_dir) / "FED_FUNDS_RATE.parquet"
    assert expected_file.exists()
