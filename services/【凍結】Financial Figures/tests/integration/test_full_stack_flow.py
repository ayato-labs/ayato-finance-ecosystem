from unittest.mock import patch

import pandas as pd
import pytest

from src.core.config import settings
from src.core.db import db_manager
from src.providers.jquants.engine import JPEngine


@pytest.fixture
def mock_jquants():
    with patch("jquantsapi.Client") as mock_client:
        mock_instance = mock_client.return_value
        yield mock_instance


def test_jp_engine_full_sync_flow(tmp_path, mock_jquants):
    """
    Integration Test: Full flow from ticker sync to fact ingestion.
    Uses mocks for the external API but real DuckDB storage.
    """
    db_path = tmp_path / "jp_integrated.duckdb"

    # Override settings for test
    with patch.object(settings, "DB_PATH_JP", db_path):
        # 1. Setup Mock Data for Tickers
        mock_jquants.get_list.return_value = pd.DataFrame(
            [
                {
                    "Code": "72030",
                    "CoName": "Toyota",
                    "MarketCodeName": "Prime",
                    "Sector17CodeName": "Transport",
                },
                {
                    "Code": "99840",
                    "CoName": "Softbank",
                    "MarketCodeName": "Prime",
                    "Sector17CodeName": "Communication",
                },
            ]
        )

        engine = JPEngine(refresh_token="fake-token")  # noqa: S106

        # 2. Sync Tickers
        count = engine.sync_tickers(session_id="test-session")
        assert count == 2

        # 3. Setup Mock Data for Statements (Wide Format)
        mock_jquants.get_fin_details.return_value = pd.DataFrame(
            [
                {
                    "LocalCode": "7203",
                    "DisclosedDate": "2023-03-31",
                    "DisclosedTime": "15:00",
                    "DisclosureNumber": "1",
                    "Type": "Annual",
                    "FiscalYear": "2023",
                    "FiscalPeriod": "FY",
                    "NetSales": 30000000.0,
                    "OperatingProfit": 2500000.0,
                }
            ]
        )

        # 4. Ingest Facts
        engine.fetch_and_ingest_statements("7203", "test-session")

        # 5. Verify DB Content
        with db_manager.connect(db_path, read_only=True) as conn:
            res = conn.execute("SELECT LocalCode, NetSales FROM company_facts").fetchone()
            assert res[0] == "7203"
            assert res[1] == 30000000.0


def test_jp_engine_retry_on_api_error(tmp_path, mock_jquants):
    """
    Evil Test: Verify retry logic when API is unstable.
    """
    db_path = tmp_path / "jp_retry.duckdb"

    with patch.object(settings, "DB_PATH_JP", db_path):
        # Fail twice, succeed on third
        mock_jquants.get_list.side_effect = [
            Exception("Rate Limit 429"),
            Exception("Internal Server Error 500"),
            pd.DataFrame(
                [
                    {
                        "Code": "12340",
                        "CoName": "Test",
                        "MarketCodeName": "T",
                        "Sector17CodeName": "S",
                    }
                ]
            ),
        ]

        # We need to reduce the retry wait for faster tests
        tenacity = pytest.importorskip("tenacity")
        with patch("tenacity.wait_exponential", return_value=tenacity.wait_fixed(0.1)):
            engine = JPEngine(refresh_token="fake-token")  # noqa: S106
            count = engine.sync_tickers()
            assert count == 1
            assert mock_jquants.get_list.call_count == 3


def test_jp_engine_malformed_api_data(tmp_path, mock_jquants):
    """
    Evil Test: Verify resilience when API returns missing columns or bad types.
    """
    db_path = tmp_path / "jp_bad_data.duckdb"

    with patch.object(settings, "DB_PATH_JP", db_path):
        # Missing mandatory columns like CoName
        mock_jquants.get_list.return_value = pd.DataFrame(
            [{"Code": "72030", "MarketCodeName": "Prime"}]
        )

        engine = JPEngine(refresh_token="fake-token")  # noqa: S106

        # Should raise KeyError as per JPEngine logic (it expects code/name)
        with pytest.raises(KeyError):
            engine.sync_tickers()


def test_jp_engine_partial_contract_failure(tmp_path, mock_jquants):
    """
    Verify that if one record is bad, others still get ingested.
    """
    db_path = tmp_path / "jp_partial.duckdb"

    with patch.object(settings, "DB_PATH_JP", db_path):
        engine = JPEngine(refresh_token="fake-token")  # noqa: S106

        # One valid, one missing required 'DisclosedDate'
        df = pd.DataFrame(
            [
                {
                    "LocalCode": "7203",
                    "DisclosedDate": "2023-01-01",
                    "DisclosedTime": "12:00",
                    "DisclosureNumber": "1",
                    "Type": "T",
                    "FiscalYear": "2023",
                    "FiscalPeriod": "FY",
                    "NetSales": 100,
                },
                {"LocalCode": "9999", "NetSales": 500},  # Missing many required fields
            ]
        )

        engine.ingest_facts("7203", df, "test-session")

        with db_manager.connect(db_path, read_only=True) as conn:
            count = conn.execute("SELECT count(*) FROM company_facts").fetchone()[0]
            assert count == 1  # Only the valid one
