import sys
import os
from pathlib import Path
from datetime import date

# Add project root to path
sys.path.append(os.getcwd())

from src.core.config import settings
from src.core.master import master_manager
from src.core.migrations import MigrationManager
from src.core.db import db_manager

def verify():
    print("=== Starting Master DB Verification ===")
    
    # 1. Trigger Migrations for Master (Bootstrap)
    print(f"Bootstrapping Master DB at {settings.DB_PATH_MASTER}...")
    # MigrationManager.apply_migrations is called internally by master_manager._ensure_master_initialized()
    # Let's just sync one shard to trigger it
    master_manager.sync_shard_status("jp", settings.DB_PATH_JP)
    
    # 2. Check if master tables exist
    with db_manager.connect(settings.DB_PATH_MASTER, read_only=True) as conn:
        tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()
        table_names = [t[0] for t in tables]
        print(f"Tables in Master DB: {table_names}")
        
        assert "shard_registry" in table_names
        assert "job_tracker" in table_names
        assert "universe_master" in table_names
        
        # 3. Check shard registry content
        registry = conn.execute("SELECT * FROM shard_registry").df()
        print("\n--- Shard Registry ---")
        print(registry)
        assert not registry.empty
        assert registry.iloc[0]['shard_id'] == 'jp'

    # 4. Test Job Tracker
    print("\nTesting Job Tracker...")
    job_id = master_manager.start_job("Verification-Test-Job", ["jp", "traceability"])
    master_manager.end_job(job_id, status="COMPLETED", records_processed=100, metadata={"test": "success"})
    
    with db_manager.connect(settings.DB_PATH_MASTER, read_only=True) as conn:
        jobs = conn.execute("SELECT * FROM job_tracker WHERE job_id = ?", [job_id]).df()
        print("\n--- Job Tracker (Last Job) ---")
        print(jobs)
        assert not jobs.empty
        assert jobs.iloc[0]['status'] == 'COMPLETED'
        assert jobs.iloc[0]['records_processed'] == 100

    print("\n=== Verification Successful! ===")

if __name__ == "__main__":
    verify()
