import threading
import time
import subprocess
import sys
import os
from pathlib import Path
import duckdb
import pytest
from edgar_core.config import settings
from edgar_core.db import db_manager

def test_single_writer_multi_reader_concurrency():
    """
    Verifies that multiple readers (API style) can access the DB 
    while a single writer (Provider style) is performing a heavy operation.
    """
    db_path = settings.DATA_DIR / "concurrency_test.duckdb"
    if db_path.exists():
        try:
            db_path.unlink()
        except: pass
    
    # Ensure DB exists and has some data
    with db_manager.connect(db_path, read_only=False) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS concurrency_test (id INTEGER, val TEXT)")
    
    # We will use two separate processes to truly test isolation
    writer_code = f"""
import time
import duckdb
from edgar_core.db import db_manager
with db_manager.connect('{db_path.as_posix()}', read_only=False) as conn:
    conn.execute("BEGIN TRANSACTION")
    for i in range(50):
        conn.execute("INSERT INTO concurrency_test VALUES (?, ?)", [i, f'val_{{i}}'])
        time.sleep(0.1)
    conn.execute("COMMIT")
print("WRITER_DONE")
"""
    
    reader_code = f"""
import time
import duckdb
from edgar_core.db import db_manager
# API mode simulation
try:
    with db_manager.connect('{db_path.as_posix()}', read_only=True) as conn:
        res = conn.execute("SELECT count(*) FROM concurrency_test").fetchone()
        print(f"READER_COUNT:{{res[0]}}")
except Exception as e:
    print(f"READER_ERROR:{{e}}")
"""

    writer_proc = subprocess.Popen(["uv", "run", "python", "-c", writer_code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    try:
        time.sleep(1) # Wait for writer to start transaction
        
        # Try multiple reads
        for i in range(3):
            result = subprocess.run(
                ["uv", "run", "python", "-c", reader_code],
                env={**os.environ, "EDGAR_COMPONENT": "api"},
                capture_output=True,
                text=True
            )
            print(f"Read {i} output: {result.stdout.strip()}")
            if result.stderr:
                print(f"Read {i} error: {result.stderr.strip()}")
            assert "READER_ERROR" not in result.stdout
            time.sleep(1)
            
    finally:
        writer_proc.terminate()
        try:
            out, err = writer_proc.communicate(timeout=5)
            print(f"Writer output: {out}")
            print(f"Writer error: {err}")
        except: pass

def test_api_component_write_protection():
    """
    Verifies that when EDGAR_COMPONENT is 'api', any write attempt fails.
    """
    code = f"""
from edgar_core.db import db_manager
import duckdb
import sys
try:
    with db_manager.connect('{settings.DB_PATH.as_posix()}') as conn:
        conn.execute("CREATE TABLE should_fail_env (id INT)")
    print("SUCCESS_UNEXPECTED")
except duckdb.InvalidInputException as e:
    if 'read-only' in str(e).lower():
        print("WRITE_PROTECTED_OK")
    else:
        print(f"FAILED_WITH_OTHER_ERROR: {{e}}")
except Exception as e:
    print(f"FAILED_WITH_EXCEPTION: {{type(e).__name__}}: {{e}}")
"""
    result = subprocess.run(
        ["uv", "run", "python", "-c", code],
        env={**os.environ, "EDGAR_COMPONENT": "api"},
        capture_output=True,
        text=True
    )
    
    if "WRITE_PROTECTED_OK" not in result.stdout:
        print(f"Protection test STDOUT: {result.stdout}")
        print(f"Protection test STDERR: {result.stderr}")
    
    assert "WRITE_PROTECTED_OK" in result.stdout

if __name__ == "__main__":
    try:
        print("Running Write Protection Test...")
        test_api_component_write_protection()
        print("Running Concurrency Test (Multi-process)...")
        test_single_writer_multi_reader_concurrency()
        print("All tests passed!")
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
