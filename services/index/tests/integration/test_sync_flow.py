import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from src.fetchers.yf_fetcher import YFinanceFetcher
from src.engine import IndexEngine
from datetime import datetime

@pytest.fixture
def integration_setup(tmp_path):
    db_dir = tmp_path / "integration_data"
    engine = IndexEngine(base_dir=str(db_dir))
    fetcher = YFinanceFetcher()
    return fetcher, engine

@patch("yfinance.download")
def test_sync_integration_success(mock_download, integration_setup):
    """Fetcherで取得したデータが正常にEngineで保存されるか"""
    fetcher, engine = integration_setup
    ticker = "^GSPC"
    
    # yfinanceのレスポンスをモック
    mock_df = pd.DataFrame({
        "Open": [4000.0], "High": [4100.0], "Low": [3900.0], "Close": [4050.0], "Volume": [1000000]
    }, index=pd.DatetimeIndex(["2024-01-01"], name="Date"))
    mock_download.return_value = mock_df
    
    # 実行
    df = fetcher.fetch(ticker, datetime(2024, 1, 1))
    assert not df.empty
    
    engine.save_data(ticker, df)
    
    # 検証
    prices = engine.get_prices(ticker)
    assert len(prices) == 1
    assert prices[0]["Close"] == 4050.0

@patch("yfinance.download")
def test_sync_integration_empty_response(mock_download, integration_setup):
    """外部APIが空を返した場合に不整合が起きないか（厳しいテスト）"""
    fetcher, engine = integration_setup
    mock_download.return_value = pd.DataFrame() # 空
    
    df = fetcher.fetch("^GSPC", datetime(2024, 1, 1))
    assert df.empty
    
    # エンジンに渡してもクラッシュしないこと
    engine.save_data("^GSPC", df)
    assert engine.get_prices("^GSPC") == []

@patch("yfinance.download")
def test_sync_integration_api_error(mock_download, integration_setup):
    """外部APIが例外を投げた場合の堅牢性（厳しいテスト）"""
    fetcher, engine = integration_setup
    mock_download.side_effect = Exception("Network Error")
    
    # エラーが発生してもプログラムが中断されず、空を返すこと
    df = fetcher.fetch("^GSPC", datetime(2024, 1, 1))
    assert df.empty
