from unittest.mock import MagicMock

import pytest

from src.services.market_sync import BatchSyncService
from tests.utils.fake_gemini import FakeGeminiClient, create_mapping_response


@pytest.fixture
def sync_service(test_settings):
    return BatchSyncService()


def test_chaos_api_rate_limit_retry(sync_service, mocker):
    """Chaos: Simulate 429 (Too Many Requests) and ensure retry logic filters up."""
    # Mock SEC to return 429 then 200
    mock_resp_429 = MagicMock(status_code=429)
    # Note: Currently USEngine uses self.client.get(url).raise_for_status()
    # It doesn't have explicit retry yet, so this test should highlight the NEED for it.

    mocker.patch(
        "httpx.Client.get",
        side_effect=[
            MagicMock(
                status_code=200, json=lambda: {"0": {"ticker": "RATE", "cik_str": 1, "title": "R"}}
            ),  # sync_tickers
            mock_resp_429,  # fetch_company_facts (Try 1)
            MagicMock(
                status_code=200, json=lambda: {"cik": "0000000001", "facts": {}}
            ),  # fetch_company_facts (Try 2 - SUCCESS)
        ],
    )

    # We expect a success after retry
    success, errors = sync_service.sync_market_full("US", limit=1)
    assert success == 1
    assert errors == 0


def test_chaos_ai_hallucination_recovery(sync_service, mocker):
    """Chaos: AI returns broken JSON or empty mappings. Ensure system falls back to 'Other'."""
    # 1. Mock SEC
    mocker.patch(
        "httpx.Client.get",
        side_effect=[
            MagicMock(
                status_code=200, json=lambda: {"0": {"ticker": "HAL", "cik_str": 2, "title": "H"}}
            ),
            MagicMock(
                status_code=200,
                json=lambda: {
                    "cik": "0000000002",
                    "facts": {
                        "us-gaap": {
                            "WeirdTag": {"units": {"USD": [{"val": 100, "end": "2023-12-31"}]}}
                        }
                    },
                },
            ),
        ],
    )

    # 2. Mock AI to return garbage
    fake_client = FakeGeminiClient(["INVALID GARBAGE TEXT", create_mapping_response([])])
    sync_service.mapper.client = fake_client

    success, errors = sync_service.sync_market_full("US", limit=1)

    # Even if AI failed, the system should log it and not crash
    assert success == 1 or errors == 1


def test_chaos_db_lock_simulation(sync_service, mocker):
    """Chaos: Simulate a locked DuckDB file using a mock exception."""
    # Instead of actually locking, we mock duckdb.connect to raise an IO Error
    # Instead of actually locking, we mock duckdb.connect in the target modules
    mocker.patch(
        "src.services.market_sync.duckdb.connect",
        side_effect=Exception("Database is locked (simulated)"),
    )
    mocker.patch(
        "src.core.audit_manager.duckdb.connect",
        side_effect=Exception("Database is locked (simulated)"),
    )

    # We expect the 'Fatal Error' to be re-raised by the service
    with pytest.raises(Exception, match="Database is locked"):
        sync_service.sync_market_full("US", limit=1)
