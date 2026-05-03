import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from src.fetchers.fred_fetcher import FredFetcher
from src.engine import MacroEngine
from datetime import datetime

@pytest.fixture
def macro_setup(tmp_path):
    engine = MacroEngine(base_dir=str(tmp_path / "macro_integration"))
    # APIキーがなくてもモックするのでOK
    fetcher = FredFetcher(api_key="fake_key")
    return fetcher, engine

@patch("fredapi.Fred.get_series")
def test_fred_integration_flow(mock_get_series, macro_setup):
    """FREDからの取得とエンジンへの保存が連携しているか"""
    fetcher, engine = macro_setup
    symbol = "DFF"
    
    # FREDのレスポンス(Series)をモック
    mock_series = pd.Series([5.33], index=pd.to_datetime(["2024-04-20"]), name="Value")
    mock_get_series.return_value = mock_series
    
    # 1. Fetch
    df = fetcher.fetch(symbol, datetime(2024, 4, 1))
    assert not df.empty
    
    # 2. Save
    engine.save_data(symbol, df)
    
    # 3. Verify
    values = engine.get_values(symbol)
    assert len(values) == 1
    assert values[0]["Value"] == 5.33
    assert values[0]["Symbol"] == "DFF"

@patch("fredapi.Fred.get_series")
def test_fred_api_error_handling(mock_get_series, macro_setup):
    """APIエラー時の耐性テスト"""
    fetcher, engine = macro_setup
    mock_get_series.side_effect = Exception("FRED API Key Invalid")
    
    df = fetcher.fetch("DFF", datetime(2024, 4, 1))
    assert df.empty # クラッシュせずに空を返すこと
