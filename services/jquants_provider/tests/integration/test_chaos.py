import pytest
import pandas as pd
from src.engine import JPEngine
from pathlib import Path


@pytest.fixture
def mock_engine(mocker):
    mocker.patch("jquantsapi.ClientV2")
    mocker.patch("jquantsapi.Client")
    test_db = Path("data/chaos_jquants.duckdb")
    if test_db.exists():
        test_db.unlink()
    engine = JPEngine(api_key="fake")
    engine.db_path = test_db
    engine._init_db()
    yield engine
    if test_db.exists():
        test_db.unlink()


def test_chaos_malformed_api_response(mock_engine, mocker):
    """
    Chaos Test: API returns data that violates schema (e.g., missing columns, wrong types).
    The system should log errors and skip invalid records instead of crashing.
    """
    # 1. Mock API with 'toxic' data
    toxic_data = pd.DataFrame(
        [
            {
                "Date": "invalid-date",
                "Code": "XXXX",
                "Open": "NOT_A_FLOAT",
            },  # This should fail validation
            {
                "Date": "2026-05-01",
                "Code": "13010",
                "Open": 100.0,
                "High": 110.0,
                "Low": 90.0,
                "Close": 105.0,
                "Volume": 1000.0,
            },  # Valid
        ]
    )
    mock_engine.cli.get_eq_bars_daily_range.return_value = toxic_data

    # 2. Execute
    mock_engine.ingest_prices(toxic_data, "chaos-session")

    # 3. Verify: Only 1 record should be in DB, and no crash occurred
    from src.core.db import db_manager

    with db_manager.connect(mock_engine.db_path) as conn:
        count = conn.execute("SELECT count(*) FROM daily_prices").fetchone()[0]
        assert count == 1


def test_chaos_database_corruption_sim(mock_engine, mocker):
    """
    Chaos Test: Simulate a read-only or locked database.
    """
    # We simulate a DuckDB error by mocking the connection execution
    mocker.patch("duckdb.DuckDBPyConnection.execute", side_effect=Exception("Database locked"))

    valid_data = pd.DataFrame(
        [
            {
                "Date": "2026-05-01",
                "Code": "13010",
                "Open": 100.0,
                "High": 110.0,
                "Low": 90.0,
                "Close": 105.0,
                "Volume": 1000.0,
            }
        ]
    )

    # Ingesting should raise an exception (or be caught and logged if that's the design)
    # Current design: JPEngine methods don't catch DB exceptions, they let them bubble up.
    with pytest.raises(Exception, match="Database locked"):
        mock_engine.ingest_prices(valid_data, "locked-test")
