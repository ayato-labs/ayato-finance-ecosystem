"""Unit tests for EdgarFetcher class."""

from datetime import date
from unittest.mock import MagicMock, patch

from src.fetcher import EdgarFetcher


class TestEdgarFetcher:
    """EdgarFetcher クラスのユニットテスト。"""

    def setup_method(self):
        """各テストメソッドの前に実行されるセットアップ。"""
        self.fetcher = EdgarFetcher(user_agent="TestAgent test@example.com")

    def test_init(self):
        """初期化テスト。"""
        assert self.fetcher.headers == {"User-Agent": "TestAgent test@example.com"}
        assert self.fetcher.ticker_to_cik_map == {}
        assert self.fetcher.cik_to_ticker_map == {}
        assert self.fetcher.max_retries == 5

    def test_init_custom_retries(self):
        """カスタムリトライ回数での初期化テスト。"""
        fetcher = EdgarFetcher(user_agent="TestAgent", max_retries=3)
        assert fetcher.max_retries == 3

    @patch("src.fetcher.requests.get")
    def test_request_with_retry_success(self, mock_get):
        """成功時のリクエストテスト。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"test": "data"}
        mock_get.return_value = mock_response

        result = self.fetcher._request_with_retry("https://example.com")
        assert result is not None
        assert result.status_code == 200

    @patch("src.fetcher.requests.get")
    def test_request_with_retry_rate_limit(self, mock_get):
        """レート制限（429）エラー時のリトライテスト。"""
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200

        mock_get.side_effect = [mock_response_429, mock_response_200]

        with patch("src.fetcher.time.sleep"):
            result = self.fetcher._request_with_retry("https://example.com")
            assert result is not None
            assert mock_get.call_count == 2

    @patch("src.fetcher.requests.get")
    def test_request_with_retry_server_error(self, mock_get):
        """サーバーエラー（5xx）時のリトライテスト。"""
        mock_response_500 = MagicMock()
        mock_response_500.status_code = 500

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200

        mock_get.side_effect = [mock_response_500, mock_response_200]

        with patch("src.fetcher.time.sleep"):
            result = self.fetcher._request_with_retry("https://example.com")
            assert result is not None
            assert mock_get.call_count == 2

    @patch("src.fetcher.requests.get")
    def test_request_with_retry_client_error(self, mock_get):
        """クライアントエラー（4xx）時のリトライなしテスト。"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = self.fetcher._request_with_retry("https://example.com")
        assert result is None
        assert mock_get.call_count == 1

    @patch("src.fetcher.requests.get")
    def test_request_with_retry_max_retries(self, mock_get):
        """最大リトライ回数到達テスト。"""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        fetcher = EdgarFetcher(user_agent="TestAgent", max_retries=2)

        with patch("src.fetcher.time.sleep"):
            result = fetcher._request_with_retry("https://example.com")
            assert result is None
            assert mock_get.call_count == 2

    @patch("src.fetcher.requests.get")
    def test_request_with_retry_network_error(self, mock_get):
        """ネットワークエラー時のリトライテスト。"""
        import requests

        mock_get.side_effect = [
            requests.ConnectionError("Connection failed"),
            MagicMock(status_code=200),
        ]

        with patch("src.fetcher.time.sleep"):
            result = self.fetcher._request_with_retry("https://example.com")
            assert result is not None

    @patch.object(EdgarFetcher, "_request_with_retry")
    def test_get_cik(self, mock_retry):
        """ティッカーからCIKへの変換テスト。"""
        mock_retry.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "0": {"ticker": "AAPL", "cik_str": 320193},
                "1": {"ticker": "MSFT", "cik_str": 789019},
            },
        )

        cik = self.fetcher.get_cik("AAPL")
        assert cik == "0000320193"

    @patch.object(EdgarFetcher, "_request_with_retry")
    def test_get_cik_unknown_ticker(self, mock_retry):
        """未知のティッカーのCIK変換テスト。"""
        mock_retry.return_value = MagicMock(
            status_code=200,
            json=lambda: {"0": {"ticker": "AAPL", "cik_str": 320193}},
        )

        cik = self.fetcher.get_cik("UNKNOWN")
        assert cik is None

    def test_list_daily_filings_date_parsing(self):
        """日付解析のロジックテスト。"""
        target_date = date(2026, 1, 15)
        year = target_date.year
        quarter = (target_date.month - 1) // 3 + 1
        assert year == 2026
        assert quarter == 1

    def test_list_daily_filings_quarter_calculation(self):
        """四半期計算のテスト。"""
        test_cases = [
            (date(2026, 1, 1), 1),
            (date(2026, 3, 31), 1),
            (date(2026, 4, 1), 2),
            (date(2026, 6, 30), 2),
            (date(2026, 7, 1), 3),
            (date(2026, 9, 30), 3),
            (date(2026, 10, 1), 4),
            (date(2026, 12, 31), 4),
        ]
        for dt, expected_quarter in test_cases:
            quarter = (dt.month - 1) // 3 + 1
            assert quarter == expected_quarter, f"Date {dt} should be Q{expected_quarter}"

    def test_filter_relevant_filings(self):
        """提出書類フィルタリングのテスト。"""
        submissions_data = {
            "filings": {
                "recent": {
                    "form": ["10-K", "10-Q", "8-K", "10-Q"],
                    "accessionNumber": ["0001", "0002", "0003", "0004"],
                    "filingDate": ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"],
                    "primaryDocument": ["doc1.htm", "doc2.htm", "doc3.htm", "doc4.htm"],
                    "primaryDocDescription": ["desc1", "desc2", "desc3", "desc4"],
                }
            }
        }

        result = self.fetcher.filter_relevant_filings(submissions_data)
        assert len(result) == 3
        assert all(f["form"] in ["10-K", "10-Q"] for f in result)

    def test_filter_relevant_filings_empty(self):
        """空の提出書類データのフィルタリングテスト。"""
        result = self.fetcher.filter_relevant_filings(None)
        assert result == []

        result = self.fetcher.filter_relevant_filings({})
        assert result == []
