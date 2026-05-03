import threading
import time

from fastapi.testclient import TestClient

from src.api.server import app
from src.services.market_sync import BatchSyncService
from tests.utils.fake_gemini import FakeGeminiClient, create_mapping_response


def test_comprehensive_user_flow(test_settings, mocker):
    """
    System Comprehensive Test:
    1. Start API Server (FastAPI TestClient)
    2. Background Sync starts (Mocked network)
    3. User queries API for synced data
    """
    mocker.patch("src.engines.us_engine.USEngine.sync_tickers", return_value=1)
    # Using 10-digit CIK for consistency with engine internal logic
    cik = "0000000001"
    mock_facts = {
        "cik": cik,
        "facts": {
            "us-gaap": {
                "Revenue": {
                    "label": "Revenue",
                    "units": {
                        "USD": [
                            {
                                "val": 5000,
                                "end": "2023-12-31",
                                "accn": "A1",
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2024-01-01",
                            }
                        ]
                    },
                }
            }
        },
    }
    mocker.patch("src.engines.us_engine.USEngine.fetch_company_facts", return_value=mock_facts)

    fake_client = FakeGeminiClient(
        [
            create_mapping_response(
                [{"tag_id": "T0", "mapped_label": "NetSales", "reasoning": "R", "confidence": 1.0}]
            )
        ]
    )

    service = BatchSyncService(start_workers=True)
    service.mapper.client = fake_client

    import duckdb

    with duckdb.connect(str(test_settings.DB_PATH_US)) as conn:
        conn.execute("INSERT INTO tickers (ticker, cik, name) VALUES ('TSLA', ?, 'Tesla')", [cik])

    service.sync_market_full("US", limit=1)
    time.sleep(1.0)
    service.wait_for_queues()

    with TestClient(app) as client:
        from src.api.server import db as server_db

        server_db.us_conn = duckdb.connect(str(test_settings.DB_PATH_US))
        server_db.jp_conn = duckdb.connect(str(test_settings.DB_PATH_JP))
        server_db.audit_conn = duckdb.connect(str(test_settings.DB_PATH_TRACEABILITY))

        response = client.get("/stats")
        assert response.status_code == 200
        assert response.json()["us_facts"] > 0

        response = client.get("/financials/TSLA")
        assert response.status_code == 200
        data = response.json()
        assert any(d["target_label"] == "NetSales" and d["value"] == 5000 for d in data)


def test_chaos_db_locking_stress(test_settings, mocker):
    """Chaos Test: Stress the DB with rapid concurrent reads while sync is writing."""
    mocker.patch("src.engines.us_engine.USEngine.sync_tickers", return_value=1)
    cik = "0000000002"

    def slow_fetch(ticker):
        time.sleep(0.05)
        return {
            "cik": cik,
            "facts": {
                "us-gaap": {
                    "T": {
                        "units": {
                            "USD": [
                                {
                                    "val": 1,
                                    "end": "2023-01-01",
                                    "accn": ticker,
                                    "fy": 2023,
                                    "fp": "FY",
                                    "form": "10-K",
                                    "filed": "2023-01-01",
                                }
                            ]
                        }
                    }
                }
            },
        }

    mocker.patch("src.engines.us_engine.USEngine.fetch_company_facts", side_effect=slow_fetch)

    service = BatchSyncService(start_workers=True)
    import duckdb

    with duckdb.connect(str(test_settings.DB_PATH_US)) as conn:
        conn.execute("INSERT INTO tickers (ticker, cik, name) VALUES ('C1', ?, 'Chaos')", [cik])

    sync_thread = threading.Thread(target=service.sync_market_full, args=("US", 1))
    sync_thread.start()

    with TestClient(app) as client:
        from src.api.server import db as server_db

        server_db.us_conn = duckdb.connect(str(test_settings.DB_PATH_US))
        for _ in range(30):
            client.get("/stats")
            client.get("/tickers?search=Chaos")
            time.sleep(0.01)

    sync_thread.join()
    service.wait_for_queues()
    assert service.session_stats["SUCCESS"] == 1
