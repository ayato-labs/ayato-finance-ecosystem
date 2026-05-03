import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import pandas as pd
from src.api.app import app, engine
import os
import shutil
from pathlib import Path

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_test_data():
    """各テストの前にデータをクリアする"""
    test_dir = "data/market_index_test"
    # エンジンの向き先をテスト用に変更
    engine.base_dir = Path(test_dir)
    if engine.base_dir.exists():
        shutil.rmtree(engine.base_dir)
    engine.base_dir.mkdir(parents=True, exist_ok=True)
    yield
    if engine.base_dir.exists():
        shutil.rmtree(engine.base_dir)

@patch("yfinance.download")
def test_full_api_workflow(mock_download):
    """同期から取得までの全フローの検証"""
    ticker = "^GSPC"
    
    # 1. データの同期 (POST)
    mock_df = pd.DataFrame({
        "Open": [4000.0], "High": [4100.0], "Low": [3900.0], "Close": [4050.0], "Volume": [1000]
    }, index=pd.DatetimeIndex(["2024-01-01"], name="Date"))
    mock_download.return_value = mock_df
    
    sync_res = client.post(f"/sync/{ticker}")
    assert sync_res.status_code == 200
    assert sync_res.json()["status"] == "success"
    
    # 2. データの取得 (GET)
    get_res = client.get(f"/prices/{ticker}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert len(data) == 1
    assert data[0]["Close"] == 4050.0

def test_get_non_existent_data():
    """存在しないデータへのアクセス(総合テスト)"""
    res = client.get("/prices/UNKNOWN_INDEX")
    assert res.status_code == 404

@patch("yfinance.download")
def test_redundant_sync_api(mock_download):
    """複数回の同期リクエスト後のデータ整合性"""
    ticker = "^GSPC"
    mock_df = pd.DataFrame({
        "Open": [4000.0], "High": [4100.0], "Low": [3900.0], "Close": [4050.0], "Volume": [1000]
    }, index=pd.DatetimeIndex(["2024-01-01"], name="Date"))
    mock_download.return_value = mock_df
    
    # 2回同期を実行
    client.post(f"/sync/{ticker}")
    client.post(f"/sync/{ticker}")
    
    # 取得結果が1件(重複排除済み)であることを確認
    res = client.get(f"/prices/{ticker}")
    assert len(res.json()) == 1
