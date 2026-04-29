from unittest.mock import patch

import pytest

from src.services.market_sync import BatchSyncService


@pytest.fixture
def mock_engines():
    with (
        patch("src.services.market_sync.USEngine") as mock_us,
        patch("src.services.market_sync.JPEngine") as mock_jp,
        patch("src.services.market_sync.audit_manager") as mock_audit,
    ):
        yield mock_us, mock_jp, mock_audit


def test_sync_market_us_full(mock_engines):
    mock_us_cls, mock_jp_cls, mock_audit = mock_engines
    mock_us_instance = mock_us_cls.return_value
    mock_audit.start_session.return_value = "test-session-id"

    # Mock duckdb query inside _sync_us_market
    with patch("duckdb.connect") as mock_db:
        mock_conn = mock_db.return_value.__enter__.return_value
        mock_conn.execute.return_value.fetchall.return_value = [("AAPL",), ("MSFT",), ("GOOGL",)]

        service = BatchSyncService()
        service.sync_market_full("US", limit=2)

        # Verify US engine called, JP engine NOT called for ingest
        assert mock_us_instance.sync_tickers.called
        assert mock_us_instance.fetch_company_facts.call_count == 2
        assert not mock_jp_cls.return_value.fetch_and_ingest_statements.called

        # Verify session management
        mock_audit.start_session.assert_called_with("US")
        mock_audit.end_session.assert_called()


def test_sync_market_jp_error_handling(mock_engines):
    mock_us_cls, mock_jp_cls, mock_audit = mock_engines
    mock_jp_instance = mock_jp_cls.return_value
    mock_audit.start_session.return_value = "jp-session"

    with patch("duckdb.connect") as mock_db:
        mock_conn = mock_db.return_value.__enter__.return_value
        mock_conn.execute.return_value.fetchall.return_value = [("8697",)]

        # Simulate error
        mock_jp_instance.fetch_and_ingest_statements.side_effect = Exception("API Limit")

        service = BatchSyncService()
        service.sync_market_full("JP")

        # Ensure error log tracked at progress level
        mock_audit.log_ticker_sync.assert_called_with("JP", "8697", 0, "ERROR: API Limit")
        # Ensure session ends successfully overall even if single ticker fails
        assert mock_audit.end_session.called
