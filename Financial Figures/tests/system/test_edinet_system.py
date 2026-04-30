import os
import subprocess
import sys
from datetime import date, timedelta

import duckdb


def test_system_edinet_cli(tmp_path):
    """
    E2E test: Run main.py with --edinet-only and verify DB creation and data.
    We use a temporary environment and custom DB path via environment variables or mock settings.
    """
    # Create a temporary directory for data
    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    db_path = data_dir / "edinet_system_test.duckdb"

    # We need to tell main.py to use this DB.
    # Since main.py uses src.core.config.settings, we can override via ENV VAR if pydantic-settings.
    env = os.environ.copy()
    env["DB_PATH_EDINET"] = str(db_path)
    env["EDINET_API_KEY"] = "DUMMY_KEY_FOR_SYSTEM_TEST"
    env["PYTHONPATH"] = "."

    # Run the CLI for a single recent date to keep it fast
    # We use a date that likely has data or at least runs through the logic
    (date.today() - timedelta(days=2)).isoformat()

    # Command: python main.py --edinet-only --sync-date <target_date>
    # Note: main.py might not have --sync-date, it uses sync_incremental internally.
    # To make it deterministic, we'll just run it.

    cmd = [sys.executable, "main.py", "--edinet-only"]

    # Run with timeout to prevent hanging
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60, check=False)

    print(f"STDOUT: {result.stdout}")
    print(f"STDERR: {result.stderr}")

    # Assert successful execution
    assert result.returncode == 0
    import re

    # Check both stdout and stderr since coloredlogs might use either
    full_output = result.stdout + result.stderr
    assert re.search(r"Starting EDINET Sync", full_output, re.IGNORECASE)

    # Verify DB existence
    assert os.path.exists(db_path)

    # Verify tables exist
    with duckdb.connect(str(db_path)) as con:
        tables = [t[0] for t in con.execute("SHOW TABLES").fetchall()]
        assert "documents" in tables
        assert "raw_facts" in tables
