import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.server import DBManager, app
from src.core.audit_manager import AuditManager
from src.services.market_sync import BatchSyncService


@pytest.fixture
def integration_env(tmp_path):
    test_data_dir = tmp_path / "test_data"
    test_data_dir.mkdir(parents=True, exist_ok=True)

    # Use exact names that server.py/settings expect
    markets_dir = test_data_dir / "markets"
    markets_dir.mkdir(parents=True, exist_ok=True)
    audit_dir = test_data_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    us_path = markets_dir / "us.duckdb"
    jp_path = markets_dir / "jp.duckdb"
    audit_path = audit_dir / "traceability.duckdb"

    return {"us": us_path, "jp": jp_path, "audit": audit_path, "data_dir": test_data_dir}


def test_full_pipeline_integration(integration_env):
    """
    End-to-end integration: Sync -> DB -> API
    """
    # Create AuditManager instance pointing to the EXACT path
    test_audit_manager = AuditManager(db_path=integration_env["audit"])

    with (
        patch("src.engines.us_engine.httpx.Client") as mock_httpx_cls,
        patch("src.engines.jp_engine.jquantsapi.ClientV2"),
        patch("src.core.audit_manager.audit_manager", test_audit_manager),
        patch("src.services.market_sync.audit_manager", test_audit_manager),
        patch("src.engines.us_engine.settings") as mock_settings_us,
        patch("src.engines.jp_engine.settings") as mock_settings_jp,
    ):
        for s in [mock_settings_us, mock_settings_jp]:
            s.DB_PATH_US = integration_env["us"]
            s.DB_PATH_JP = integration_env["jp"]
            s.DATA_DIR = integration_env["data_dir"]
            s.db_read_only = False

        mock_us_client = mock_httpx_cls.return_value
        mock_us_client.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"1": {"ticker": "AAPL", "cik_str": 320193, "title": "Apple Inc."}},
        )

        with patch("src.engines.us_engine.USEngine.fetch_company_facts") as mock_fetch:
            mock_fetch.return_value = {
                "cik": "0000320193",
                "facts": {
                    "us-gaap": {
                        "NetIncomeLoss": {
                            "units": {
                                "USD": [
                                    {
                                        "val": 100,
                                        "end": "2023-12-31",
                                        "accn": "a1",
                                        "fy": 2023,
                                        "fp": "FY",
                                    }
                                ]
                            }
                        }
                    }
                },
            }

            # RUN SYNC
            sync_service = BatchSyncService()
            sync_service.us_engine.db_path = integration_env["us"]
            sync_service.us_engine._init_db()
            sync_service.sync_market_full("US", limit=1)

    # Verify Sync result
    assert os.path.exists(integration_env["us"])
    # Create mapping audit entries in the ALREADY initialized audit file
    test_audit_manager.log_mapping(
        "test-session", "US:NetIncomeLoss", "NetIncome", "logic", 1.0, "test-gemma"
    )

    # CRITICAL: Start API with settings pointing exactly to our test_data_dir
    with patch("src.api.server.settings") as mock_settings_api:
        mock_settings_api.DB_PATH_US = integration_env["us"]
        mock_settings_api.DB_PATH_JP = integration_env["jp"]
        mock_settings_api.DB_PATH_TRACEABILITY = integration_env["audit"]
        mock_settings_api.DATA_DIR = integration_env["data_dir"]

        # Now DBManager will attach correctly
        test_db_manager = DBManager()

        with patch("src.api.server.db", test_db_manager):
            client = TestClient(app)

            # End-to-End unified join check
            res_fin = client.get("/financials/AAPL")
            assert res_fin.status_code == 200
            data = res_fin.json()
            assert data[0]["target_label"] == "NetIncome"
            assert data[0]["value"] == 100.0
