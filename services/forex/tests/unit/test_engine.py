import pandas as pd

from src.engine import ForexEngine


def test_forex_engine_save_and_get_latest(temp_forex_dir):
    engine = ForexEngine(temp_forex_dir)

    # テストデータの作成
    expected_latest_rate = 0.0071
    df = pd.DataFrame(
        {
            "Date": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")],
            "Symbol": ["JPY", "JPY"],
            "Rate": [0.007, expected_latest_rate],
            "LoadTimestamp": [pd.Timestamp.now(), pd.Timestamp.now()],
        }
    )

    engine.save_data("JPY", df)

    # 最新日付の取得
    latest_date = engine.get_latest_date("JPY")
    assert latest_date == pd.Timestamp("2024-01-02")

    # 最新レートの取得
    latest_rate = engine.get_latest_rate("JPY")
    assert latest_rate == expected_latest_rate


def test_forex_engine_deduplication(temp_forex_dir):
    """同じ日付のデータが複数ある場合、新しいLoadTimestampが優先されることを確認"""
    engine = ForexEngine(temp_forex_dir)

    t1 = pd.Timestamp("2024-05-01 10:00:00")
    t2 = pd.Timestamp("2024-05-01 11:00:00")

    df1 = pd.DataFrame(
        {
            "Date": [pd.Timestamp("2024-01-01")],
            "Symbol": ["JPY"],
            "Rate": [0.007],
            "LoadTimestamp": [t1],
        }
    )
    engine.save_data("JPY", df1)

    new_rate = 0.008
    df2 = pd.DataFrame(
        {
            "Date": [pd.Timestamp("2024-01-01")],
            "Symbol": ["JPY"],
            "Rate": [new_rate],  # レートが変わったとする
            "LoadTimestamp": [t2],
        }
    )
    engine.save_data("JPY", df2)

    rates = engine.get_rates("JPY")
    assert len(rates) == 1
    assert rates[0]["Rate"] == new_rate
