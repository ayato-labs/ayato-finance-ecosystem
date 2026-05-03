import pytest
from src.batch_fetch import batch_fetch
from src.storage import FinancialNarrativeStorage

def test_system_e2e_flow(mocker, temp_db_path, sample_html, mock_filing_metadata):
    """
    ユーザーフロー全体のテスト:
    取得(Mocked) -> パース(Real) -> 保存(Real)
    """
    # 依存コンポーネントの設定
    mocker.patch("src.batch_fetch.FinancialNarrativeStorage", return_value=FinancialNarrativeStorage(temp_db_path))
    mocker.patch("src.batch_fetch.TICKERS", ["AAPL"])
    
    # ネットワーク通信のみモック化(SECへの負荷防止)
    mock_fetcher = mocker.patch("src.batch_fetch.EdgarFetcher")
    mock_fetcher.return_value.get_latest_submissions.return_value = {"filings": {"recent": {}}}
    mock_fetcher.return_value.filter_relevant_filings.return_value = [mock_filing_metadata]
    mock_fetcher.return_value.get_cik.return_value = "320193"
    
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.status_code = 200
    mock_get.return_value.text = sample_html
    
    # 全体フローの実行
    batch_fetch()
    
    # 最終結果の検証: DuckDBに期待通りのレコードが存在するか
    storage = FinancialNarrativeStorage(temp_db_path)
    summary = storage.get_summary()
    assert len(summary) == 1
    assert summary[0][0] == "AAPL"
    assert summary[0][1] == "10-K"
