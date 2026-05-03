import os
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from src.backend.main import aggregator, app, db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db():
    # 絶対パスでテスト用DBを指定
    test_db = os.path.abspath("test_system.duckdb")
    if os.path.exists(test_db):
        os.remove(test_db)

    # main.py の db インスタンスを一時的に差し替え
    old_db_path = db.db_path
    db.db_path = test_db
    db._init_db()

    yield

    # 元に戻す & 削除
    db.db_path = old_db_path
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except:
            pass


def test_user_transaction_lifecycle():
    # 外部APIのモック化
    aggregator.get_latest_price = AsyncMock(return_value=160.0)
    aggregator.get_benchmark_performance = AsyncMock(return_value=5.0)
    aggregator.get_historical_prices = AsyncMock(return_value=[150.0, 155.0, 160.0])

    # 1. 取引の登録 (POST)
    payload = {
        "ticker": "AAPL",
        "type": "BUY",
        "asset_type": "STOCK",
        "quantity": 10.0,
        "price": 150.0,
        "timestamp": "2024-01-01T10:00:00",
        "fee": 1.0,
        "memo": "Test Trade",
    }
    response = client.post("/transactions", json=payload)
    assert response.status_code == 200
    tx_id = response.json()["id"]

    # 2. 取引履歴の取得 (GET)
    response = client.get("/transactions")
    assert response.status_code == 200
    assert any(tx["id"] == tx_id for tx in response.json())

    # 3. ダッシュボード(ポートフォリオ)の取得 (GET)
    response = client.get("/portfolio")
    assert response.status_code == 200
    data = response.json()
    assert data["total_market_value"] == 1600.0  # 10 * 160.0
    assert data["gain_percent"] > 0
    assert data["volatility"] is not None

    # 4. 取引の編集 (PUT)
    update_payload = payload.copy()
    update_payload["quantity"] = 20.0
    response = client.put(f"/transactions/{tx_id}", json=update_payload)
    assert response.status_code == 200

    # 5. 編集後の再確認
    response = client.get("/portfolio")
    assert response.json()["total_market_value"] == 3200.0  # 20 * 160.0

    # 6. 取引の削除 (DELETE)
    response = client.delete(f"/transactions/{tx_id}")
    assert response.status_code == 200

    # 7. 最終確認
    response = client.get("/portfolio")
    assert response.json()["total_market_value"] == 0


def test_api_error_handling():
    # 厳しいテスト: 存在しない取引の編集
    response = client.put(
        "/transactions/9999",
        json={
            "ticker": "FAIL",
            "type": "BUY",
            "asset_type": "STOCK",
            "quantity": 1,
            "price": 100,
            "timestamp": "2024-01-01T00:00:00",
        },
    )
    assert response.status_code == 404

    # 厳しいテスト: 不正なデータ形式での登録
    response = client.post("/transactions", json={"ticker": "AAPL"})
    assert response.status_code == 422
