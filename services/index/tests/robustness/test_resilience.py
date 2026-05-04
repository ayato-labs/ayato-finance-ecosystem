import pandas as pd

from src.engine import IndexEngine


def test_index_engine_robustness(tmp_path):
    """異常系・負荷テスト"""
    db_path = tmp_path / "test_index.duckdb"
    engine = IndexEngine(str(db_path))

    # 1. 巨大データの保存
    large_df = pd.DataFrame({
        "Date": pd.date_range("2000-01-01", periods=10000),
        "Ticker": ["LARGE"] * 10000,
        "Close": [100.0] * 10000,
        "Source": ["test"] * 10000,
        "LoadTimestamp": [pd.Timestamp.now()] * 10000
    })
    engine.save_data("LARGE", large_df)

    res = engine.get_latest_date("LARGE")
    assert res is not None

    # 2. 空のデータフレーム
    engine.save_data("EMPTY", pd.DataFrame())

    # 3. カラム欠損 (スキーマ違反)
    bad_df = pd.DataFrame({"Date": [pd.Timestamp.now()]})
    engine.save_data("BAD", bad_df)
    # get_prices は DuckDBを使用しており、カラム不足で失敗するはず
    prices = engine.get_prices("BAD")
    assert prices == []  # エラーログが出て空リストが返るはず


def test_concurrent_api_requests(mocker):
    """APIエンドポイントへの並列アクセス耐性 (疑似)"""
    pass
