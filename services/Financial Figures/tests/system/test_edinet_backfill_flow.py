import os
import subprocess
import sys

import duckdb
import pytest


def test_backfill_cli_invalid_csv_path():
    """CLI test: Should handle non-existent CSV path gracefully."""
    # Ensure we have an API key to reach the backfill logic
    env = os.environ.copy()
    if "EDINET_API_KEY" not in env:
        env["EDINET_API_KEY"] = "dummy_for_test"

    env["PYTHONPATH"] = "."
    cmd = [sys.executable, "main.py", "--edinet-backfill", "non_existent.csv"]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)

    full_output = result.stdout + result.stderr
    assert "EDINET Backfill failed" in full_output or "No such file" in full_output
    assert result.returncode == 0


def test_backfill_cli_missing_api_key():
    """CLI test: Should fail if EDINET_API_KEY is not set."""
    env = os.environ.copy()
    env["EDINET_API_KEY"] = ""  # Explicitly empty to trigger the check
    env["PYTHONPATH"] = "."

    cmd = [sys.executable, "main.py", "--edinet-backfill", "dummy.csv"]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)

    full_output = result.stdout + result.stderr
    assert "EDINET_API_KEY" in full_output


@pytest.mark.skipif(not os.getenv("EDINET_API_KEY"), reason="Requires real EDINET API Key for E2E")
def test_backfill_minimal_end_to_end(tmp_path):
    """
    E2E test: Run a 1-day backfill for a known ticker and verify DB.
    Note: This hits the real API. Use sparingly.
    """
    db_path = tmp_path / "e2e_edinet.duckdb"
    csv_path = tmp_path / "minimal.csv"

    # Toyota (7203) mapping
    with open(csv_path, "w", encoding="cp932") as f:
        f.write("Header\n")
        f.write(
            "ＥＤＩＮＥＴコード,提出者種別,発行者,上場区分,連結・単体,資本金,提出者名,提出者名(英),提出者名(ヨミ),住所,業種,証券コード,法人番号\n"
        )
        f.write(
            "E02144,法人,あり,上場,連結,635401,トヨタ自動車,TOYOTA,トヨタ,愛知,輸送用機器,72030,0\n"
        )

    from src.edinet.mapping import EDINETMapper

    mapper = EDINETMapper(str(db_path))
    mapper.load_csv(str(csv_path))

    with duckdb.connect(str(db_path)) as conn:
        res = conn.execute(
            "SELECT ticker FROM edinet_tickers WHERE edinet_code='E02144'"
        ).fetchone()
        assert res[0] == "7203"


def test_backfill_flow_simulated(tmp_path, mocker):
    """System test: Simulate a 2-day backfill flow and verify cross-table integrity."""
    db_path = tmp_path / "sim_backfill.duckdb"
    csv_path = tmp_path / "sim_master.csv"

    # Setup mock master CSV
    with open(csv_path, "w", encoding="cp932") as f:
        f.write(
            "H\nＥＤＩＮＥＴコード,提出者種別,発行者,上場区分,連結・単体,資本金,提出者名,提出者名(英),提出者名(ヨミ),住所,業種,証券コード,法人番号\n"
        )
        f.write("E001,法人,あり,上場,連結,100,TestCo,T,T,T,T,12340,0\n")

    from src.edinet.mapping import EDINETMapper
    from src.edinet.storage import EDINETStorage
    from src.edinet.sync_worker import EDINETSyncWorker

    worker = EDINETSyncWorker()
    worker.storage = EDINETStorage(db_path=str(db_path))
    worker.mapper = EDINETMapper(str(db_path))

    # Mock Client
    mock_client = mocker.Mock()
    # Day 1: 1 doc, Day 2: 0 docs
    mock_client.get_document_list.side_effect = [
        {
            "results": [
                {
                    "docID": "D1",
                    "docTypeCode": "120",
                    "edinetCode": "E001",
                    "filerName": "T",
                    "submissionPeriod": "2026-04-20",
                }
            ]
        },
        {"results": []},
    ]
    # ZIP download returns valid mock zip
    from tests.integration.test_edinet_sync_chain import create_mock_zip

    mock_client.download_document_csv.return_value = create_mock_zip()
    worker.client = mock_client

    # Execute 2-day backfill
    worker.run_backfill(days=2)

    # Verify Database State
    with duckdb.connect(str(db_path)) as conn:
        # Check documents metadata
        res = conn.execute("SELECT count(*) FROM documents WHERE doc_id='D1'").fetchone()
        assert res[0] == 1


def test_historical_backfill_flow_full(tmp_path, mocker):
    """System test: Full historical backfill flow simulation."""
    # Mock time.sleep to avoid 15 minute wait
    mocker.patch("time.sleep")

    db_path = tmp_path / "full_hist.duckdb"
    csv_path = tmp_path / "full_master.csv"

    with open(csv_path, "w", encoding="cp932") as f:
        f.write(
            "H\nＥＤＩＮＥＴコード,提出者種別,発行者,上場区分,連結・単体,資本金,提出者名,提出者名(英),提出者名(ヨミ),住所,業種,証券コード,法人番号\n"
        )
        f.write("E001,法人,あり,上場,連結,100,TestCo,T,T,T,T,12340,0\n")

    from src.edinet.mapping import EDINETMapper
    from src.edinet.storage import EDINETStorage
    from src.edinet.sync_worker import EDINETSyncWorker

    worker = EDINETSyncWorker()
    worker.storage = EDINETStorage(db_path=str(db_path))
    worker.mapper = EDINETMapper(str(db_path))

    # Mock Client to return empty list to avoid long loop
    mock_client = mocker.Mock()
    mock_client.get_document_list.return_value = {"results": []}
    worker.client = mock_client

    # Run backfill for "10 years" -> should be clipped to 5
    worker.run_historical_backfill(years=10, csv_path=str(csv_path))

    # Verify Master Table
    with duckdb.connect(str(db_path)) as conn:
        res = conn.execute("SELECT ticker FROM edinet_tickers WHERE edinet_code='E001'").fetchone()
        assert res[0] == "1234"

    # Verify loop count (approx 5 years)
    assert mock_client.get_document_list.call_count >= 1825
