import duckdb

from src.core.audit_manager import AuditManager


def test_audit_manager_session_lifecycle(tmp_path):
    # Setup test DB path
    test_db = tmp_path / "traceability.duckdb"
    am = AuditManager(db_path=test_db)

    # 1. Start Session
    session_id = am.start_session(market="US")
    assert session_id is not None

    # Check DB
    with duckdb.connect(str(test_db)) as conn:
        row = conn.execute(
            "SELECT market, status FROM sync_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        assert row[0] == "US"
        assert row[1] == "STARTED"

    # 2. End Session
    am.end_session(session_id, status="SUCCESS", records=10, errors=0)

    with duckdb.connect(str(test_db)) as conn:
        row = conn.execute(
            "SELECT status, records_processed FROM sync_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        assert row[0] == "SUCCESS"
        assert row[1] == 10


def test_audit_manager_log_mapping(tmp_path):
    test_db = tmp_path / "traceability.duckdb"
    am = AuditManager(db_path=test_db)

    am.log_mapping(
        session_id="test-session",
        source="US:Assets",
        target="TotalAssets",
        model="test-gemma",
        reasoning="Test reasoning",
        confidence=0.95,
    )

    with duckdb.connect(str(test_db)) as conn:
        row = conn.execute(
            "SELECT target_label, reasoning FROM mapping_audit WHERE source_tag = 'US:Assets'"
        ).fetchone()
        assert row[0] == "TotalAssets"
        assert row[1] == "Test reasoning"


def test_audit_manager_sync_progress(tmp_path):
    test_db = tmp_path / "traceability.duckdb"
    am = AuditManager(db_path=test_db)

    # 1. Log progress
    am.log_ticker_sync("US", "AAPL", 100, "SUCCESS")
    am.log_ticker_sync("JP", "8697", 50, "ERROR: Timeout")

    with duckdb.connect(str(test_db)) as conn:
        rows = conn.execute("SELECT symbol, status FROM sync_progress ORDER BY symbol").fetchall()
        assert rows[0][0] == "8697"
        assert rows[0][1] == "ERROR: Timeout"
        assert rows[1][0] == "AAPL"
        assert rows[1][1] == "SUCCESS"

    # 2. Test filter for sync
    to_sync = am.get_tickers_to_sync("JP")
    # Tickers with ERROR should be returned
    assert "8697" in to_sync
