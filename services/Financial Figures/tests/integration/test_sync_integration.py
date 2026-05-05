import time

from src.services.market_sync import BatchSyncService
from tests.utils.fake_gemini import FakeGeminiClient, create_mapping_response


def test_integration_full_sync_flow(test_settings, mocker):
    """Integration test: Verify the flow from fetch -> DB Queue -> AI Queue -> DB Storage."""
    # 1. Setup mocks for external network calls
    mocker.patch("src.providers.sec_edgar.engine.USEngine.sync_tickers", return_value=1)

    mock_facts = {
        "cik": "0000320193",
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": {
                    "label": "Net Income",
                    "units": {
                        "USD": [
                            {
                                "val": 1000,
                                "end": "2023-09-30",
                                "accn": "1",
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2023-10-01",
                            }
                        ]
                    },
                }
            }
        },
    }
    mocker.patch("src.providers.sec_edgar.engine.USEngine.fetch_company_facts", return_value=mock_facts)

    # 2. Setup Fake Gemini for AI mapping
    fake_response = create_mapping_response(
        [
            {
                "tag_id": "T0",
                "mapped_label": "Profit",
                "reasoning": "Direct match",
                "confidence": 1.0,
            }
        ]
    )
    fake_client = FakeGeminiClient([fake_response])

    # 3. Execute sync
    service = BatchSyncService()
    service.mapper.client = fake_client

    # Pre-populate tickers table
    import duckdb

    with duckdb.connect(str(service.us_engine.db_path)) as conn:
        conn.execute(
            "INSERT INTO tickers (ticker, cik, name) VALUES ('AAPL', '0000320193', 'Apple')"
        )

    # Run the sync for one ticker
    service.sync_market_full("US", limit=1)

    # Wait extra time for AI/DB threads to finish their task done
    time.sleep(0.5)
    service.wait_for_queues()

    # 4. Verification
    with duckdb.connect(str(service.us_engine.db_path)) as conn:
        val = conn.execute("SELECT value FROM company_facts WHERE cik = '0000320193'").fetchone()[0]
        assert val == 1000

    with duckdb.connect(str(test_settings.DB_PATH_TRACEABILITY)) as conn:
        mapping = conn.execute(
            "SELECT mapped_label FROM mapping_audit WHERE source_tag = 'US:NetIncomeLoss'"
        ).fetchone()
        assert mapping is not None
        assert mapping[0] == "Profit"


def test_integration_error_resilience(test_settings, mocker):
    """Resilience test: Verify that a single ticker fetch failure doesn't stop the whole sync."""
    mocker.patch("src.providers.sec_edgar.engine.USEngine.sync_tickers", return_value=2)

    def mock_fetch(ticker):
        if ticker == "FAIL":
            raise Exception("Network error")
        return {"cik": "2", "facts": {}}

    mocker.patch("src.providers.sec_edgar.engine.USEngine.fetch_company_facts", side_effect=mock_fetch)

    service = BatchSyncService()

    import duckdb

    with duckdb.connect(str(service.us_engine.db_path)) as conn:
        conn.execute("""
            INSERT INTO tickers (ticker, cik, name)
            VALUES ('FAIL', '1', 'F'), ('SUCCESS', '2', 'S')
        """)

    service.sync_market_full("US", limit=2)

    assert service.session_stats["SUCCESS"] == 1
    assert service.session_stats["ERROR"] == 1
