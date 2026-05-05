import pytest
import pandas as pd
from src.engine import JPEngine
from pathlib import Path


@pytest.fixture
def mock_engine(mocker):
    # Mock J-Quants Client to avoid real API calls in integration tests
    mocker.patch("jquantsapi.ClientV2")
    mocker.patch("jquantsapi.Client")

    # Use a temporary DuckDB for testing
    test_db = Path("data/test_jquants.duckdb")
    if test_db.exists():
        test_db.unlink()

    # Force use of API key to trigger ClientV2
    engine = JPEngine(api_key="fake-key")
    engine.db_path = test_db
    engine._init_db()

    yield engine

    if test_db.exists():
        test_db.unlink()


def test_fetch_to_ingest_prices_flow(mock_engine, mocker):
    """
    Integration test: Fetch range -> Ingest into DB.
    Tests if data flows correctly through the system.
    """
    # 1. Setup mock data
    mock_data = pd.DataFrame(
        [
            {
                "Date": "2026-05-01",
                "Code": "13010",
                "Open": 100,
                "High": 110,
                "Low": 90,
                "Close": 105,
                "Volume": 1000,
            },
            {
                "Date": "2026-05-02",
                "Code": "13010",
                "Open": 105,
                "High": 115,
                "Low": 100,
                "Close": 112,
                "Volume": 1500,
            },
        ]
    )
    mock_engine.cli.get_eq_bars_daily_range.return_value = mock_data

    # 2. Execute flow
    session_id = "test-integration"
    df = mock_engine.fetch_prices_range("20260501", "20260502")
    mock_engine.ingest_prices(df, session_id)

    # 3. Verify DB state
    from src.core.db import db_manager

    with db_manager.connect(mock_engine.db_path) as conn:
        count = conn.execute("SELECT count(*) FROM daily_prices").fetchone()[0]
        assert count == 2

        # Test differential sync part (same record shouldn't be added)
        mock_engine.ingest_prices(df, session_id)
        count_again = conn.execute("SELECT count(*) FROM daily_prices").fetchone()[0]
        assert count_again == 2  # Still 2 due to INSERT OR IGNORE


def test_error_resilience_rate_limit(mock_engine, mocker):
    """
    Chaos test: Ensure the system handles 429 errors with retries.
    """
    # Mock API to raise 429 once, then succeed
    mock_call = mocker.patch.object(mock_engine.cli, "get_list")

    # In a real scenario, jquantsapi might raise custom errors,
    # but we test the engine's retry logic.
    mock_call.side_effect = [
        Exception("too many 429 error responses"),
        pd.DataFrame([{"Code": "1301", "CoName": "A", "MktNm": "B", "S17Nm": "C"}]),
    ]

    # We need to speed up the retry wait for tests
    mocker.patch("time.sleep", return_value=None)

    count = mock_engine.sync_tickers("chaos-test")
    assert count == 1
    assert mock_call.call_count == 2
