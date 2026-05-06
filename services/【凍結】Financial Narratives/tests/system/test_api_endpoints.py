import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.db.master_db import JobQueue
from src.storage import FinancialNarrativeStorage

client = TestClient(app)


def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert "service" in response.json()


def test_get_status(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_api.duckdb")
    master_path = str(tmp_path / "test_master.sqlite")

    # ENVを上書きしてDIがテスト用DBを向くようにする
    with monkeypatch.context() as m:
        m.setenv("DEFAULT_DB_PATH", db_path)
        # JobQueueのデフォルトパスは現状ハードコード気味なので、
        # 必要なら JobQueue 側で環境変数を見るように修正すべきだが、
        # ここでは直接初期化して整合性を取る。
        storage = FinancialNarrativeStorage(db_path=db_path)
        queue = JobQueue(db_path=master_path)
        queue._init_db()

        # FastAPIのDependencyをオーバーライド
        app.dependency_overrides[FinancialNarrativeStorage] = lambda: storage
        app.dependency_overrides[JobQueue] = lambda: queue

        response = client.get("/status")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert "total_filings" in data
        assert "pipeline_stats" in data
        assert data["pipeline_stats"]["PENDING"] == 0


@pytest.mark.asyncio
async def test_get_ticker_analysis_not_found():
    response = client.get("/analysis/NONEXISTENT")
    assert response.status_code == 404
