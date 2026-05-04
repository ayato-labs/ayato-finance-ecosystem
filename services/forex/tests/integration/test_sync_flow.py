from datetime import datetime

import pandas as pd
import pytest

from src.engine import ForexEngine
from src.fetchers.forex_fetcher import ForexFetcher


def test_forex_sync_integration(mocker, temp_forex_dir):
    """FetcherとEngineを組み合わせた同期フローのテスト"""
    engine = ForexEngine(temp_forex_dir)
    fetcher = ForexFetcher()

    # yfinanceの呼び出しをモック化 (結合テストなので)
    mock_history = mocker.patch("yfinance.Ticker.history")
    idx = pd.to_datetime(["2024-05-01", "2024-05-02"])
    idx.name = "Date"
    mock_history.return_value = pd.DataFrame({"Close": [150.0, 151.0]}, index=idx)

    symbol = "JPY"
    start_date = datetime(2024, 5, 1)

    # 1. 取得
    df = fetcher.fetch(symbol, start_date)
    assert not df.empty

    # 2. 保存
    engine.save_data(symbol, df)

    # 3. 検証
    latest_rate = engine.get_latest_rate(symbol)
    # 1 JPY = 1/151.0 USD
    assert latest_rate == pytest.approx(1.0 / 151.0)

    rates = engine.get_rates(symbol)
    expected_count = 2
    assert len(rates) == expected_count
