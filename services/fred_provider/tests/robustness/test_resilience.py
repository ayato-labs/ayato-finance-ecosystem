import pandas as pd
from src.engine import MacroEngine


def test_macro_engine_robustness(tmp_path):
    """異常系テスト"""
    engine = MacroEngine(str(tmp_path))

    # 1. 巨大データ
    large_df = pd.DataFrame(
        {
            "Date": pd.date_range("2000-01-01", periods=5000),
            "Symbol": ["LARGE"] * 5000,
            "Value": [1.0] * 5000,
            "Source": ["test"] * 5000,
            "LoadTimestamp": [pd.Timestamp.now()] * 5000,
        }
    )
    engine.save_data("LARGE", large_df)
    assert engine.get_latest_date("LARGE") is not None

    # 2. スキーマ不一致データ
    bad_df = pd.DataFrame({"WrongColumn": [1]})
    engine.save_data("BAD", bad_df)
    data = engine.get_values("BAD")
    assert data == []  # DuckDBクエリで失敗して空リストになるはず
