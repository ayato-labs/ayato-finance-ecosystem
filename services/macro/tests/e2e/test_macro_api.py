import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import pandas as pd
from src.api.app import app, engine
import shutil
from pathlib import Path

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_test_data():
    """テストごとにデータをクリア"""
    test_dir = Path("data/macro_test_e2e")
    engine.base_dir = test_dir
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)
    yield
    if test_dir.exists():
        shutil.rmtree(test_dir)

@patch("fredapi.Fred.get_series")
def test_macro_api_full_workflow(mock_get_series):
    """同期 -> 取得 のE2Eテスト"""
    symbol = "DGS10"
    
    # 1. FREDデータのモック
    mock_series = pd.Series([4.5], index=pd.to_datetime(["2024-04-25"]), name="Value")
    mock_get_series.return_value = mock_series
    
    # 2. 同期リクエスト (POST)
    # すでに生成されているapp.fetcherの内部をパッチし、戻り値を設定する
    from src.api.app import fetcher as app_fetcher
    with patch.object(app_fetcher, "fred", MagicMock()) as mock_fred:
        mock_fred.get_series.return_value = mock_series
        res_sync = client.post(f"/sync/{symbol}")
        assert res_sync.status_code == 200
        assert res_sync.json()["status"] == "success"
    
    # 3. 取得リクエスト (GET)
    res_get = client.get(f"/indicators/{symbol}")
    assert res_get.status_code == 200
    data = res_get.json()
    assert len(data) == 1
    assert data[0]["Value"] == 4.5
    assert data[0]["Date"] == "2024-04-25"

def test_api_not_found():
    """存在しない指標へのアクセス"""
    res = client.get("/indicators/INVALID_SYMBOL")
    assert res.status_code == 404
