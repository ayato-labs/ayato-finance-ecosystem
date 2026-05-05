import pytest
from pathlib import Path
import duckdb
from src.core.master import MasterManager
from src.core.db import db_manager

def test_master_initialization(master_manager):
    """Test that master database is correctly initialized with required tables."""
    with db_manager.connect(master_manager.db_path, read_only=True) as conn:
        tables = conn.execute("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]
        assert "shard_registry" in table_names
        assert "job_tracker" in table_names  # Fixed from job_log

def test_sync_shard_status(master_manager, tmp_path):
    """Test shard registration and status synchronization."""
    from src.core.migrations import MigrationManager
    shard_path = tmp_path / "test_shard.duckdb"
    # Properly initialize the shard so _schema_version exists
    MigrationManager.apply_migrations(str(shard_path), "edinet_raw")
    
    master_manager.sync_shard_status("test_shard", shard_path)
    
    with db_manager.connect(master_manager.db_path, read_only=True) as conn:
        res = conn.execute("SELECT shard_id, physical_path, health_status FROM shard_registry").fetchone()
        assert res[0] == "test_shard"
        assert Path(res[1]) == shard_path
        assert res[2] == "HEALTHY"

def test_job_lifecycle(master_manager):
    """Test starting and ending a job."""
    job_id = master_manager.start_job("Test-Job", affected_shards=["shard_1"])
    assert job_id is not None
    
    with db_manager.connect(master_manager.db_path, read_only=True) as conn:
        job = conn.execute("SELECT job_name, status FROM job_tracker WHERE job_id = ?", [job_id]).fetchone()
        assert job[0] == "Test-Job"
        assert job[1] == "RUNNING"
        
    master_manager.end_job(job_id, status="COMPLETED", metadata={"processed": 100})
    
    with db_manager.connect(master_manager.db_path, read_only=True) as conn:
        job = conn.execute("SELECT status, metadata FROM job_tracker WHERE job_id = ?", [job_id]).fetchone()
        assert job[0] == "COMPLETED"
        assert "processed" in job[1]

def test_sync_shard_not_found(master_manager, tmp_path):
    """Test behavior when shard path does not exist."""
    fake_path = tmp_path / "non_existent.duckdb"
    # Should not raise exception, but log warning (internal behavior)
    master_manager.sync_shard_status("fake", fake_path)
    
    with db_manager.connect(master_manager.db_path, read_only=True) as conn:
        res = conn.execute("SELECT COUNT(*) FROM shard_registry WHERE shard_id = 'fake'").fetchone()
        assert res[0] == 0
