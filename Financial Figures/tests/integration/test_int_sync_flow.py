from unittest.mock import MagicMock

import duckdb
import pytest

from src.core.config import settings
from src.services.market_sync import BatchSyncService


@pytest.fixture
def sync_service(test_settings):
    # We mock the internal engines to avoid real network
    service = BatchSyncService()
    return service


def test_full_sync_flow_us(sync_service, mocker):
    """
    Test the full US sync flow:
    1. Mock SEC Tickers API
    2. Mock SEC CompanyFacts API
    3. Mock Gemini Client responses (via mapping table logic)
    4. Run sync
    5. Check standardized data via manual join
    """
    # 1. Mock SEC Tickers
    mock_tickers = {"0": {"ticker": "TEST", "cik_str": "0000012345", "title": "Test Co"}}
    mocker.patch(
        "httpx.Client.get",
        side_effect=[
            MagicMock(status_code=200, json=lambda: mock_tickers),  # sync_tickers
            MagicMock(
                status_code=200,
                json=lambda: {  # fetch_company_facts
                    "cik": "0000012345",
                    "facts": {
                        "us-gaap": {
                            "NetSales": {
                                "units": {
                                    "USD": [{"val": 500, "end": "2023-12-31", "accn": "TEST-ACCN"}]
                                }
                            }
                        }
                    },
                },
            ),
        ],
    )

    # 2. Mock AI Mapper responses
    from tests.utils.fake_gemini import FakeGeminiClient, create_mapping_response

    fake_ai_resp = create_mapping_response(
        [{"tag_id": "T0", "mapped_label": "NetSales", "reasoning": "Direct Match"}]
    )
    fake_client = FakeGeminiClient([fake_ai_resp])

    # Inject fake client into the service's mapper
    sync_service.mapper.client = fake_client

    # Manually log the mapping to the audit DB so the join works in verification
    from src.core.audit_manager import audit_manager

    audit_manager.log_mapping("session-test", "US:NetSales", "NetSales", "Direct Match")

    # 3. Run sync for 1 ticker
    success, errors = sync_service.sync_market_full("US", limit=1)

    assert success == 1
    assert errors == 0

    # 4. Verify DB via manual join (no reliance on pre-created view)
    with duckdb.connect(str(settings.DB_PATH_US)) as conn:
        audit_db_posix = settings.DB_PATH_TRACEABILITY.as_posix()
        conn.execute(f"ATTACH '{audit_db_posix}' AS audit")
        res = conn.execute("""
            SELECT m.mapped_label, f.value
            FROM main.company_facts f
            JOIN audit.mapping_audit m ON m.source_tag = 'US:' || f.tag
            WHERE f.cik = '0000012345'
        """).fetchall()
        assert len(res) == 1
        assert res[0][0] == "NetSales"
        assert res[0][1] == 500.0
