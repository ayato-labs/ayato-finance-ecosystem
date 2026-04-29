from unittest.mock import patch

import duckdb
import pytest
from fastapi.testclient import TestClient

from src.api.server import app, db

client = TestClient(app)


@pytest.fixture
def setup_api_db(tmp_path):
    # Create temp DBs for US, JP and Audit
    us_db = tmp_path / "us.duckdb"
    jp_db = tmp_path / "jp.duckdb"
    audit_db = tmp_path / "traceability.duckdb"

    # Initialize schemas
    with duckdb.connect(str(us_db)) as conn_us:
        conn_us.execute("CREATE TABLE tickers (ticker VARCHAR, name VARCHAR, cik VARCHAR)")
        conn_us.execute("INSERT INTO tickers VALUES ('AAPL', 'Apple Inc.', '0000320193')")
        conn_us.execute(
            "CREATE TABLE company_facts (tag VARCHAR, value DOUBLE, unit VARCHAR, "
            "end_date DATE, fiscal_year INTEGER, cik VARCHAR)"
        )
        conn_us.execute(
            "INSERT INTO company_facts VALUES ('NetIncome', 1000, 'USD', '2024-01-01', 2024, '0000320193')"
        )

    with duckdb.connect(str(jp_db)) as conn_jp:
        conn_jp.execute(
            "CREATE TABLE tickers (code VARCHAR, name VARCHAR, "
            "market_section VARCHAR, sector VARCHAR)"
        )
        conn_jp.execute("INSERT INTO tickers VALUES ('86970', 'JPX', 'Prime', 'Finance')")
        conn_jp.execute(
            "CREATE TABLE company_facts (code VARCHAR, tag VARCHAR, value DOUBLE, "
            "unit VARCHAR, disclosed_date DATE, fiscal_year INTEGER, "
            "accession_number VARCHAR)"
        )
        conn_jp.execute(
            "INSERT INTO company_facts VALUES ('86970', 'NP', 500, 'JPY', '2024-01-01', 2024, 'acc-1')"
        )

    with duckdb.connect(str(audit_db)) as conn_audit:
        conn_audit.execute(
            "CREATE TABLE mapping_audit (id VARCHAR PRIMARY KEY, source_tag VARCHAR, "
            "target_label VARCHAR, reasoning TEXT, session_id VARCHAR, "
            "ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        conn_audit.execute(
            "INSERT INTO mapping_audit (id, source_tag, target_label, reasoning, session_id) "
            "VALUES ('m1', 'US:NetIncome', 'NetIncome', 'Reason US', 's1')"
        )
        conn_audit.execute(
            "INSERT INTO mapping_audit (id, source_tag, target_label, reasoning, session_id) "
            "VALUES ('m2', 'JP:NP', 'NetIncome', 'Reason JP', 's2')"
        )

    return us_db, jp_db, audit_db


def test_api_unified_financials(setup_api_db, test_settings):
    us_db, jp_db, audit_db = setup_api_db
    with patch("src.api.server.settings", test_settings):
        if db.conn:
            db.conn.close()
        db.conn = duckdb.connect(str(us_db))
        db.conn.execute(f"ATTACH '{jp_db}' AS jp")
        db.conn.execute(f"ATTACH '{audit_db}' AS audit")
        db._create_unified_views()

        response = client.get("/financials/AAPL")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert data[0]["market"] == "US"

        response = client.get("/financials/8697")
        assert response.status_code == 200
        assert response.json()[0]["market"] == "JP"


def test_api_tickers_filtering_and_pagination(setup_api_db, test_settings):
    us_db, jp_db, audit_db = setup_api_db
    if db.conn:
        db.conn.close()
    db.conn = duckdb.connect(str(us_db))
    db.conn.execute(f"ATTACH '{jp_db}' AS jp")

    # 1. Search
    response = client.get("/tickers?search=apple")
    assert response.status_code == 200
    assert any(t["symbol"] == "AAPL" for t in response.json())

    # 2. Pagination
    response = client.get("/tickers?limit=1&offset=0")
    assert len(response.json()) == 1

    # 3. Market filter
    response = client.get("/tickers?market=JP")
    assert all(t["market"] == "JP" for t in response.json())


def test_api_stats(setup_api_db, test_settings):
    us_db, jp_db, audit_db = setup_api_db
    if db.conn:
        db.conn.close()
    db.conn = duckdb.connect(str(us_db))
    db.conn.execute(f"ATTACH '{jp_db}' AS jp")
    db.conn.execute(f"ATTACH '{audit_db}' AS audit")
    # Add a dummy session to audit for stats
    db.conn.execute(
        "CREATE TABLE IF NOT EXISTS audit.sync_sessions (session_id VARCHAR PRIMARY KEY)"
    )

    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert "us_tickers" in data
    assert data["us_tickers"] == 1
