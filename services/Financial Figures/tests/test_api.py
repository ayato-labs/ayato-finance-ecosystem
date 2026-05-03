from unittest.mock import patch

import duckdb
import pytest
from fastapi.testclient import TestClient

from src.api.server import app

client = TestClient(app)


@pytest.fixture
def setup_api_data(test_settings):
    # Use paths from test_settings
    us_db = test_settings.DB_PATH_US
    jp_db = test_settings.DB_PATH_JP
    audit_db = test_settings.DB_PATH_TRACEABILITY

    # Initialize schemas
    with duckdb.connect(str(us_db)) as conn_us:
        conn_us.execute(
            "CREATE TABLE IF NOT EXISTS tickers (ticker VARCHAR, name VARCHAR, cik VARCHAR)"
        )
        conn_us.execute("INSERT INTO tickers VALUES ('AAPL', 'Apple Inc.', '0000320193')")
        conn_us.execute(
            "CREATE TABLE IF NOT EXISTS company_facts (tag VARCHAR, value DOUBLE, unit VARCHAR, "
            "end_date DATE, fiscal_year INTEGER, cik VARCHAR)"
        )
        conn_us.execute(
            "INSERT INTO company_facts VALUES "
            "('NetIncome', 1000, 'USD', '2024-01-01', 2024, '0000320193')"
        )

    with duckdb.connect(str(jp_db)) as conn_jp:
        conn_jp.execute(
            "CREATE TABLE IF NOT EXISTS tickers (code VARCHAR, name VARCHAR, "
            "market_section VARCHAR, sector VARCHAR)"
        )
        conn_jp.execute("INSERT INTO tickers VALUES ('8697', 'JPX', 'Prime', 'Finance')")
        conn_jp.execute(
            "CREATE TABLE IF NOT EXISTS company_facts (code VARCHAR, tag VARCHAR, value DOUBLE, "
            "unit VARCHAR, disclosed_date DATE, fiscal_year INTEGER, "
            "accession_number VARCHAR)"
        )
        conn_jp.execute(
            "INSERT INTO company_facts VALUES ('8697', 'NP', 500, 'JPY', '2024-01-01', 2024, "
            "'acc-1')"
        )

    with duckdb.connect(str(audit_db)) as conn_audit:
        conn_audit.execute("""
            CREATE TABLE IF NOT EXISTS mapping_audit (
                mapping_id VARCHAR PRIMARY KEY,
                session_id VARCHAR,
                source_tag VARCHAR,
                mapped_label VARCHAR,
                reasoning VARCHAR,
                confidence_score DOUBLE,
                mapped_at TIMESTAMP,
                llm_model_version VARCHAR
            )
        """)
        conn_audit.execute(
            "INSERT INTO mapping_audit (mapping_id, source_tag, mapped_label, "
            "reasoning, session_id) VALUES ('m1', 'US:NetIncome', 'NetIncome', 'Reason US', 's1')"
        )
        conn_audit.execute(
            "INSERT INTO mapping_audit (mapping_id, source_tag, mapped_label, "
            "reasoning, session_id) VALUES ('m2', 'JP:NP', 'NetIncome', 'Reason JP', 's2')"
        )

    return us_db, jp_db, audit_db


def test_api_unified_financials(setup_api_data, test_settings):
    with patch("src.api.server.settings", test_settings):
        response = client.get("/financials/AAPL")
        assert response.status_code == 200  # noqa: PLR2004
        data = response.json()
        assert len(data) > 0
        assert data[0]["market"] == "US"

        response = client.get("/financials/8697")
        assert response.status_code == 200  # noqa: PLR2004
        assert response.json()[0]["market"] == "JP"


def test_api_tickers_filtering_and_pagination(setup_api_data, test_settings):
    # 1. Search
    response = client.get("/tickers?search=apple")
    assert response.status_code == 200  # noqa: PLR2004
    assert any(t["symbol"] == "AAPL" for t in response.json())

    # 2. Pagination
    response = client.get("/tickers?limit=1&offset=0")
    assert len(response.json()) == 1

    # 3. Market filter
    response = client.get("/tickers?market=JP")
    assert all(t["market"] == "JP" for t in response.json())


def test_api_stats(setup_api_data, test_settings):
    _, _, audit_db = setup_api_data
    # Add a dummy session to audit for stats
    with duckdb.connect(str(audit_db)) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS sync_sessions (session_id VARCHAR PRIMARY KEY)")

    response = client.get("/stats")
    assert response.status_code == 200  # noqa: PLR2004
    data = response.json()
    assert "us_tickers" in data
    assert data["us_tickers"] == 1
