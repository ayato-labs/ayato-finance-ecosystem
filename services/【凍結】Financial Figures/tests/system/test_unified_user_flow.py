import time
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.server import app
from src.core.config import settings


@pytest.fixture
def api_client():
    return TestClient(app)


def test_unified_system_flow(tmp_path, api_client):
    """
    Comprehensive System Test:
    1. Check Health
    2. Trigger Sync for a JP Symbol
    3. Verify Financials Retrieval

    We mock the J-Quants API at the engine level.
    """
    db_path_jp = tmp_path / "jp_system.duckdb"
    db_path_us = tmp_path / "us_system.duckdb"
    db_path_audit = tmp_path / "audit_system.duckdb"
    db_path_edinet = tmp_path / "edinet_system.duckdb"

    with (
        patch.object(settings, "DB_PATH_JP", db_path_jp),
        patch.object(settings, "DB_PATH_US", db_path_us),
        patch.object(settings, "DB_PATH_TRACEABILITY", db_path_audit),
        patch.object(settings, "DB_PATH_EDINET", db_path_edinet),
    ):
        # 1. Health Check
        response = api_client.get("/health")
        assert response.status_code == 200

        # 2. Mock J-Quants for the background sync
        # We need to patch where JPEngine is used (BatchSyncService)
        # Or more simply, patch the client inside the engine instance
        mock_data = pd.DataFrame(
            [
                {
                    "LocalCode": "7203",
                    "DisclosedDate": "2023-03-31",
                    "DisclosedTime": "15:00",
                    "DisclosureNumber": "1",
                    "Type": "Annual",
                    "FiscalYear": "2023",
                    "FiscalPeriod": "FY",
                    "NetSales": 40000000.0,
                    "OperatingProfit": 3000000.0,
                }
            ]
        )

        # Mocking the fetch_statements call in the JP engine
        from src.api.server import sync_service

        sync_service.jp_engine.fetch_statements = MagicMock(return_value=mock_data)

        # Setup all shards in DB
        from src.core.db import db_manager
        from src.core.migrations import MigrationManager

        MigrationManager.apply_migrations(db_path_jp, "jp")
        MigrationManager.apply_migrations(db_path_us, "us")
        MigrationManager.apply_migrations(db_path_edinet, "edinet")
        MigrationManager.apply_migrations(db_path_audit, "traceability")

        # VERY IMPORTANT: Redirect the existing instances in the API server
        from src.api.server import sync_service
        from src.core.audit_manager import audit_manager

        sync_service.jp_engine.db_path = db_path_jp
        sync_service.us_engine.db_path = db_path_us
        audit_manager._db_path_override = db_path_audit

        with db_manager.connect(db_path_jp, read_only=False) as conn:
            conn.execute("INSERT INTO tickers (code, name) VALUES ('7203', 'Toyota')")

        # 3. Trigger Sync via API
        # We disable the background thread and do it manually for the test if possible,
        # but here we follow the API flow.
        sync_response = api_client.post("/sync/7203")
        assert sync_response.status_code == 200
        assert sync_response.json()["status"] == "accepted"

        # Wait for background queue processing (it's very fast in memory)
        time.sleep(1)

        # 4. Get Financials
        fin_response = api_client.get("/financials/7203")

        # If the background worker hasn't finished, this might be 404.
        # Let's retry a few times.
        for _ in range(5):
            if fin_response.status_code == 200:
                break
            time.sleep(1)
            fin_response = api_client.get("/financials/7203")

        assert fin_response.status_code == 200
        data = fin_response.json()
        assert len(data) > 0
        # Verify the wide-format mapping works
        sales_record = next(r for r in data if r["target_label"] == "NetSales")
        assert sales_record["value"] == 40000000.0
        assert sales_record["reasoning"] == "Direct J-Quants Native Mapping"


def test_api_error_handling(tmp_path, api_client):
    """
    Evil System Test: Invalid symbol, non-existent symbol.
    """
    db_path_jp = tmp_path / "jp_err.duckdb"
    db_path_us = tmp_path / "us_err.duckdb"
    db_path_audit = tmp_path / "audit_err.duckdb"
    db_path_edinet = tmp_path / "edinet_err.duckdb"

    with (
        patch.object(settings, "DB_PATH_JP", db_path_jp),
        patch.object(settings, "DB_PATH_US", db_path_us),
        patch.object(settings, "DB_PATH_TRACEABILITY", db_path_audit),
        patch.object(settings, "DB_PATH_EDINET", db_path_edinet),
    ):
        from src.core.migrations import MigrationManager

        MigrationManager.apply_migrations(db_path_jp, "jp")
        MigrationManager.apply_migrations(db_path_us, "us")
        MigrationManager.apply_migrations(db_path_edinet, "edinet")
        MigrationManager.apply_migrations(db_path_audit, "traceability")

        # 1. Invalid symbol format
        response = api_client.get("/financials/INVALID")
        assert response.status_code == 404  # Not found in DB

        # 2. Missing required params for tickers
        response = api_client.get("/tickers?search=")
        # Depends on validation, but if min_length=1, might 422
        assert response.status_code in [200, 422]
