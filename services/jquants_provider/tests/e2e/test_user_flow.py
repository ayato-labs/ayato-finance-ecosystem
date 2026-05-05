import pytest
import tempfile
from pathlib import Path
from main import main
import sys

def test_full_sync_cli_flow(mocker):
    """
    E2E Test: Simulate running 'main.py --sync-tickers' and verify it completes.
    """
    tmpdir = tempfile.TemporaryDirectory()
    base_path = Path(tmpdir.name)
    
    # Mock settings
    mocker.patch("src.core.config.settings.DATA_DIR", base_path)
    mocker.patch("src.core.config.settings.MASTER_DB_PATH", str(base_path / "master.duckdb"))
    
    # Mock engine to avoid real heavy sync
    mocker.patch("src.engine.JPEngine.sync_tickers", return_value=10)
    
    # Simulate CLI args
    sys.argv = ["main.py", "--sync-tickers"]
    
    # Execute main
    try:
        main()
    except SystemExit as e:
        assert e.code == 0
        
    # Verify master shard exists (created by MigrationManager during JPEngine init in main)
    assert (base_path / "master.duckdb").exists()
    tmpdir.cleanup()

def test_cli_failure_exit_code(mocker):
    """
    E2E Test: Verify that a fatal error in engine results in exit code 1.
    """
    mocker.patch("src.engine.JPEngine.sync_tickers", side_effect=Exception("Critical Failure"))
    
    sys.argv = ["main.py", "--sync-tickers"]
    
    with pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 1
