import pandas as pd
from fastapi import status
from fastapi.testclient import TestClient

from src.api.app import app, get_engine
from src.engine import ForexEngine


def test_forex_api_workflow(temp_forex_dir):
    """APIを介したエンドツーエンドのフロー確認"""
    test_engine = ForexEngine(temp_forex_dir)
    app.dependency_overrides[get_engine] = lambda: test_engine

    client = TestClient(app)

    # 0. 初期状態 (データなし)
    resp = client.get("/latest/JPY")
    assert resp.status_code == status.HTTP_404_NOT_FOUND

    # 1. データの準備 (Engineを直接叩いて投入)
    expected_rate = 0.0065
    df = pd.DataFrame({
        "Date": [pd.Timestamp("2024-05-01")],
        "Symbol": ["JPY"],
        "Rate": [expected_rate],
        "LoadTimestamp": [pd.Timestamp.now()]
    })
    test_engine.save_data("JPY", df)

    # 2. APIで最新レート取得
    resp = client.get("/latest/JPY")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["rate"] == expected_rate

    # 3. 履歴取得
    resp = client.get("/rates/JPY")
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 1

    # クリーンアップ
    app.dependency_overrides.clear()
