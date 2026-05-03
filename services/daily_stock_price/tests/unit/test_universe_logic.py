from unittest.mock import MagicMock, patch

from src.universe import UniverseManager


def test_us_universe_fallback_no_key(temp_data_dir):
    """Verify that UniverseManager falls back to Wikipedia if no FMP key is provided."""
    manager = UniverseManager(cache_dir=str(temp_data_dir / "universe"), fmp_api_key=None)

    # Mocking the Wikipedia request to avoid external hits
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.text = (
            "<table><tr><th>Symbol</th><th>Security</th></tr>"
            "<tr><td>AAPL</td><td>Apple</td></tr></table>"
        )
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        tickers = manager.get_us_universe()
        assert "AAPL" in tickers
        assert (temp_data_dir / "universe" / "us_tickers.csv").exists()

def test_us_universe_fmp_integration(temp_data_dir):
    """Verify that UniverseManager uses FMP when a key is provided."""
    manager = UniverseManager(cache_dir=str(temp_data_dir / "universe"), fmp_api_key="fake_key")

    # Mock FMP JSON response
    fmp_data = [
        {"symbol": "TSLA", "name": "Tesla", "exchangeShortName": "NASDAQ"},
        {"symbol": "MSFT", "name": "Microsoft", "exchangeShortName": "NASDAQ"},
        {"symbol": "NON_US", "name": "Foreign", "exchangeShortName": "LSE"}
    ]

    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = fmp_data
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        tickers = manager.get_us_universe()
        assert "TSLA" in tickers
        assert "MSFT" in tickers
        assert "NON_US" not in tickers # Should be filtered out
        assert (temp_data_dir / "universe" / "us_tickers_full.csv").exists()

def test_us_universe_fmp_failure_fallback(temp_data_dir):
    """Verify that if FMP fails (e.g., 401), it falls back to Wikipedia."""
    manager = UniverseManager(cache_dir=str(temp_data_dir / "universe"), fmp_api_key="bad_key")

    with patch("requests.get") as mock_get:
        # First call (FMP) fails
        mock_resp_fmp = MagicMock()
        mock_resp_fmp.raise_for_status.side_effect = Exception("Unauthorized")

        # Second call (Wikipedia) succeeds
        mock_resp_wiki = MagicMock()
        mock_resp_wiki.text = (
            "<table><tr><th>Symbol</th><th>Security</th></tr>"
            "<tr><td>GOOG</td><td>Google</td></tr></table>"
        )
        mock_resp_wiki.status_code = 200

        mock_get.side_effect = [mock_resp_fmp, mock_resp_wiki]

        tickers = manager.get_us_universe()
        assert "GOOG" in tickers
