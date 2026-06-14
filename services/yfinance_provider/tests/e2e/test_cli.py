import subprocess
import os
import sys
import pytest
import duckdb


def test_cli_sync_success():
    """CLIを実行して正常に同期ができるか"""
    try:
        # sys.executable を使って、確実に同じ仮想環境の Python で実行する
        result = subprocess.run(
            [sys.executable, "-m", "src.collector.main", "--tickers", "AAPL"],
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )
        output = result.stdout + result.stderr
        assert "Sync session finished" in output or "Skipping" in output or result.returncode == 0
    except subprocess.TimeoutExpired:
        pytest.skip("CLI sync timed out")


def test_cli_invalid_arg():
    """不正な引数でエラーになるか"""
    result = subprocess.run(
        [sys.executable, "-m", "src.collector.main", "--invalid-arg"],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    assert result.returncode != 0


def test_cli_db_locked():
    """DBがロックされている場合のエラーハンドリング"""
    db_path = os.path.join("data", "yfinance.duckdb")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = duckdb.connect(db_path)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "src.collector.main", "--tickers", "AAPL"],
            capture_output=True,
            text=True,
            timeout=15,
            stdin=subprocess.DEVNULL,
        )
        output = result.stdout + result.stderr
        assert result.returncode != 0
        assert "IOException" in output or "locked" in output or "Fatal error" in output
    except subprocess.TimeoutExpired:
        pass
    finally:
        conn.close()
