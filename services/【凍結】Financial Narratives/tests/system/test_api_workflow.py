from fastapi.testclient import TestClient

from src.api.app import app, get_queue, get_storage
from src.db.master_db import JobQueue
from src.storage import FinancialNarrativeStorage


def test_api_full_workflow(mocker, tmp_path):
    """
    APIを通じた一連のユーザーフローのテスト。
    1. 同期リクエストの送信
    2. ステータス確認
    3. 取得データの確認
    """
    db_path = str(tmp_path / "test_lake.duckdb")
    master_path = str(tmp_path / "test_master.sqlite")

    # テスト用DBを使用するように依存性を注入
    test_storage = FinancialNarrativeStorage(db_path)
    test_queue = JobQueue(db_path=master_path)
    test_queue._init_db()

    app.dependency_overrides[get_storage] = lambda: test_storage
    app.dependency_overrides[get_queue] = lambda: test_queue

    client = TestClient(app)

    # 0. 初期状態確認
    resp = client.get("/status")
    assert resp.status_code == 200
    assert resp.json()["total_filings"] == 0
    assert resp.json()["pipeline_stats"]["PENDING"] == 0

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


def test_api_reconcile_and_stats(tmp_path):
    """ReconcileのAPI呼び出しと統計反映の確認"""
    db_path = str(tmp_path / "test_lake.duckdb")
    master_path = str(tmp_path / "test_master.sqlite")

    test_storage = FinancialNarrativeStorage(db_path)
    test_queue = JobQueue(db_path=master_path)
    test_queue._init_db()

    app.dependency_overrides[get_storage] = lambda: test_storage
    app.dependency_overrides[get_queue] = lambda: test_queue

    client = TestClient(app)

    # 1件未構造化データを仕込む
    test_storage.save_filing(
        {
            "accessionNumber": "REC-001",
            "ticker": "RECO",
            "form": "10-Q",
            "filingDate": "2024-05-01",
        },
        {"mda": "need structuring"},
    )

    # Reconcileを同期的に実行するようにモック
    from src.reconciler import Reconciler

    def mock_reconcile():
        r = Reconciler()
        r.storage_jp.db_path = db_path
        r.storage_us.db_path = db_path  # 同じDBを使う
        r.queue.db_path = master_path
        r.run()

    # NOTE: BackgroundTasks は TestClient では別スレッドで走るが、
    # ここではシンプルに動作後の queue を確認する。
    # API経由で reconcile を叩く
    resp = client.post("/reconcile")
    assert resp.status_code == 200

    # 実際のスレッド実行を待たずに、手動で走らせて結果を確認（単体テスト的）
    mock_reconcile()

    resp = client.get("/status")
    assert resp.json()["pipeline_stats"]["PENDING"] >= 1

    app.dependency_overrides.clear()
