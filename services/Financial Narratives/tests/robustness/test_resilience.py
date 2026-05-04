import time

from src.edgar_fetcher import EdgarFetcher
from src.edinet_fetcher import EdinetFetcher


def test_edgar_fetcher_retry_logic(mocker):
    """429エラー時にリトライが行われるかを確認"""
    fetcher = EdgarFetcher("TestAgent", max_retries=2)

    mock_get = mocker.patch("requests.get")
    # 1回目は429、2回目も429
    mock_get.return_value.status_code = 429

    # リトライ時のスリープを短縮して高速化
    mocker.patch("time.sleep")

    start_time = time.time()
    fetcher.get_latest_submissions("AAPL")
    end_time = time.time()

    # 2回呼ばれているはず (初回 + リトライ1回)
    assert mock_get.call_count == 2
    # time.sleepが呼ばれているはず
    assert time.sleep.call_count == 2


def test_edinet_fetcher_malformed_json(mocker):
    """EDINETが不正なJSONを返した場合の堅牢性"""
    fetcher = EdinetFetcher()
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.side_effect = ValueError("Invalid JSON")

    from datetime import date

    docs = fetcher.list_documents(date(2024, 5, 1))
    assert docs == []


def test_edinet_fetcher_server_down(mocker):
    """サーバーダウン時の挙動"""
    fetcher = EdinetFetcher()
    mock_get = mocker.patch("requests.get", side_effect=Exception("Server Down"))

    from datetime import date

    docs = fetcher.list_documents(date(2024, 5, 1))
    assert docs == []


def test_storage_concurrency_stress(temp_db_path):
    """並列保存時の負荷テスト (簡易版)"""
    import threading

    from src.storage import FinancialNarrativeStorage

    storage = FinancialNarrativeStorage(temp_db_path)

    def worker(i):
        metadata = {
            "accessionNumber": f"CONC-{i}",
            "ticker": "STRESS",
            "form": "10-K",
            "filingDate": "2024-01-01",
        }
        storage.save_filing(metadata, {"content": "data" * 1000})

    threads = []
    for i in range(20):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    summary = storage.get_summary()
    assert len(summary) == 20
