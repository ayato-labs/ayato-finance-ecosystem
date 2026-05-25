import pytest
import asyncio
from unittest.mock import MagicMock, patch
from src.edgar_fetcher import EdgarFetcher
from src.edinet_fetcher import EdinetFetcher


@pytest.mark.asyncio
async def test_edgar_rate_limit_backoff():
    """SEC APIのレート制限（429）発生時にリトライされるかを検証"""
    fetcher = EdgarFetcher("TestAgent")

    # requests.get が 429 を返した後に 200 を返すように設定
    with patch("src.edgar_fetcher.requests.get") as mock_get:
        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.headers = {"Retry-After": "0.1"}

        mock_200 = MagicMock()
        mock_200.status_code = 200
        # SECのcompany_tickers.jsonは "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."} という形式
        mock_200.json.return_value = {
            "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}
        }

        # 1回目はTickerMapの更新、2回目はSubmissionsの取得として振る舞わせる必要がある
        # 実際には get_latest_submissions 内で get_cik -> _refresh_ticker_map が呼ばれる

        # モックの動作をより正確に：1回目(429), 2回目(TickerMap), 3回目(Submissions)
        mock_submissions = MagicMock()
        mock_submissions.status_code = 200
        mock_submissions.json.return_value = {"cik": "320193", "filings": {"recent": {"form": []}}}

        mock_get.side_effect = [mock_429, mock_200, mock_submissions]

        res = fetcher.get_latest_submissions("AAPL")
        assert res is not None
        assert mock_get.call_count == 3


def test_storage_invalid_metadata():
    """不正なメタデータで保存しようとした際のエラーハンドリング"""
    from src.storage import FinancialNarrativeStorage
    import os

    storage = FinancialNarrativeStorage(":memory:")

    # 必須フィールドが欠落している場合
    bad_metadata = {"ticker": "AAPL"}  # accessionNumber 等が欠落
    with pytest.raises(ValueError, match="Missing required metadata fields"):
        storage.save_filing(bad_metadata, {"content": "test"})
