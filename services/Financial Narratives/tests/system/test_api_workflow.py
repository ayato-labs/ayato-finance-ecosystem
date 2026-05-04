from fastapi.testclient import TestClient

from src.api.app import app, get_storage
from src.storage import FinancialNarrativeStorage


def test_api_full_workflow(mocker, temp_db_path):
    """
    APIを通じた一連のユーザーフローのテスト。
    1. 同期リクエストの送信
    2. ステータス確認
    3. 取得データの確認
    """
    # テスト用DBを使用するように依存性を注入
    test_storage = FinancialNarrativeStorage(temp_db_path)
    app.dependency_overrides[get_storage] = lambda: test_storage

    client = TestClient(app)

    # 0. 初期状態確認
    resp = client.get("/status")
    assert resp.status_code == 200
    assert resp.json()["total_filings"] == 0

    # 1. 同期リクエスト (POST /sync/{ticker})
    # batch_fetch自体は時間がかかるため、中身をモック化して即座に終了・保存するようにする
    def mock_batch_fetch(tickers=None, **kwargs):
        if tickers:
            for t in tickers:
                test_storage.save_filing(
                    {
                        "accessionNumber": f"ACC-{t}",
                        "ticker": t,
                        "form": "10-K",
                        "filingDate": "2024-01-01",
                    },
                    {"mda": f"Content for {t}"},
                )

    # BackgroundTasksで呼ばれる関数をモック
    mocker.patch("src.api.app.batch_fetch", side_effect=mock_batch_fetch)

    resp = client.post("/sync/AAPL")
    assert resp.status_code == 200
    assert resp.json()["status"] == "processing"

    # 2. 本来は非同期だが、モックで即保存したのでデータを直接確認
    # (実際のシステムテストではウェイトやポーリングが必要だが、
    # ここでは同期的に動作するようにモックした)
    resp = client.get("/narratives/AAPL")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "AAPL"
    assert data[0]["sections"]["mda"] == "Content for AAPL"

    # 3. 存在しない銘柄
    resp = client.get("/narratives/UNKNOWN")
    assert resp.status_code == 200
    assert resp.json() == []

    # クリーンアップ
    app.dependency_overrides.clear()


def test_api_error_handling(temp_db_path):
    """APIのエラーハンドリング確認"""
    # 読み取り専用ファイルなどでDB接続エラーを模倣 (簡易的にNoneを渡すなど)
    app.dependency_overrides[get_storage] = lambda: None  # 不正なインスタンス

    client = TestClient(app)
    resp = client.get("/status")
    assert resp.status_code == 500

    app.dependency_overrides.clear()
