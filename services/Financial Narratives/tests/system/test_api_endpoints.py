import pytest
from fastapi.testclient import TestClient
from src.api.app import app
from src.storage import FinancialNarrativeStorage
import os

client = TestClient(app)

def test_api_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "Financial Narratives API" in response.json()["service"]

def test_api_status(tmp_path):
    db_path = str(tmp_path / "api_test.duckdb")
    with pytest.MonkeyPatch().context() as m:
        m.setenv("DEFAULT_DB_PATH", db_path)
        # 再初期化
        storage = FinancialNarrativeStorage(db_path)
        response = client.get("/status")
        assert response.status_code == 200
        assert "total_filings" in response.json()

def test_api_sync_ticker():
    # 実際には同期せず、タスクが登録されたことだけを確認
    response = client.post("/sync/AAPL")
    assert response.status_code == 200
    assert "Sync and Structuring started" in response.json()["message"]
