import pytest

from src.storage import FinancialNarrativeStorage


@pytest.mark.asyncio
async def test_incremental_update_logic(mocker, temp_db_path, sample_html, mock_filing_metadata):
    # 1. 依存コンポーネントのモック化
    # Storageをテスト用一時DBに向ける
    mocker.patch(
        "src.batch_fetch.FinancialNarrativeStorage",
        return_value=FinancialNarrativeStorage(temp_db_path),
    )

    # Fetcherの挙動をモック化
    mock_fetcher = mocker.patch("src.batch_fetch.EdgarFetcher")
    mock_instance = mock_fetcher.return_value
    mock_instance.get_latest_submissions.return_value = {"filings": {"recent": {}}}
    mock_instance.filter_relevant_filings.return_value = [mock_filing_metadata]
    mock_instance.get_cik.return_value = "0001234567"

    # ネットワークリクエストのモック化
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.status_code = 200
    mock_get.return_value.text = sample_html

    # Tickerリストをテスト用に制限
    mocker.patch("src.batch_fetch.TICKERS", ["TEST"])

    from src.batch_fetch import batch_fetch

    # 2. 実行 (1回目: 新規取得)
    await batch_fetch()

    # 1回目は JP(7日分の一覧取得) + US(1件の取得) = 8回
    assert mock_get.call_count == 8

    # 3. 実行 (2回目: 差分更新によりUSの取得はスキップされるはず)
    await batch_fetch()

    # 2回目は JP(7日分の一覧取得) = 7回増えて、合計15回
    assert mock_get.call_count == 15
