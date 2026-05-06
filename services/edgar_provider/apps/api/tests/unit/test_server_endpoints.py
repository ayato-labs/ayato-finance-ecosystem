import zstandard as zstd
from edgar_api.server import app
from edgar_core.config import settings
from edgar_core.db import db_manager
from fastapi.testclient import TestClient

client = TestClient(app)


def test_api_endpoints_real_db(tmp_path, monkeypatch):
    """
    Unit Test: Verify API endpoints using a real temporary database.
    No mocks allowed (hits the actual server code and db).
    """
    test_db = tmp_path / "api_unit.duckdb"
    # Patch settings to use our test db
    monkeypatch.setattr(settings, "DB_PATH", test_db)

    # Initialize schema
    with db_manager.connect(test_db, read_only=False) as conn:
        conn.execute(
            """
            CREATE TABLE company_facts (
                ticker TEXT, label TEXT, value DOUBLE,
                fiscal_year INTEGER, fiscal_period TEXT,
                filed_date DATE, form TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO company_facts VALUES ("
            "'AAPL', 'Assets', 100.0, 2023, 'FY', '2024-01-01', '10-K')"
        )

        conn.execute(
            "CREATE TABLE narratives ("
            "ticker TEXT, section_name TEXT, content_md_zstd BLOB, filed_date DATE)"
        )
        # We need compressed content for narratives
        cctx = zstd.ZstdCompressor()
        compressed = cctx.compress(b"Risk context")
        conn.execute(
            "INSERT INTO narratives VALUES ('AAPL', 'Risk Factors', ?, '2024-01-01')", [compressed]
        )

    # Test /tickers
    response = client.get("/tickers")
    assert response.status_code == 200
    assert "AAPL" in response.json()["tickers"]

    # Test /financials
    response = client.get("/financials/AAPL")
    assert response.status_code == 200
    assert response.json()[0]["label"] == "Assets"

    # Test /narratives
    response = client.get("/narratives/AAPL")
    assert response.status_code == 200
    assert "Risk context" in response.json()[0]["content"]


def test_api_404_handling(tmp_path, monkeypatch):
    """Unit Test: Verify 404 behavior."""
    test_db = tmp_path / "api_404.duckdb"
    monkeypatch.setattr(settings, "DB_PATH", test_db)

    with db_manager.connect(test_db, read_only=False) as conn:
        conn.execute("CREATE TABLE company_facts (ticker TEXT)")

    response = client.get("/financials/MISSING")
    assert response.status_code == 404
