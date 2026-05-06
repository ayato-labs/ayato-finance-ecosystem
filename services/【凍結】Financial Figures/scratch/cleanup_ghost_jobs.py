import duckdb
from src.core.config import settings

def cleanup_jobs():
    current_job_id = "3c69b3cb-9030-4d23-afe5-018cd13a3fc2"
    conn = duckdb.connect(str(settings.DB_PATH_MASTER), read_only=False)
    
    # Mark old running jobs as FAILED
    conn.execute("""
        UPDATE job_tracker 
        SET status = 'FAILED', 
            error_message = 'Interrupted by system restart',
            ended_at = CURRENT_TIMESTAMP
        WHERE job_name = 'EDINET-Backfill' 
          AND status = 'RUNNING' 
          AND job_id != ?
    """, [current_job_id])
    
    print("Ghost jobs cleanup executed.")
    conn.close()

if __name__ == "__main__":
    cleanup_jobs()
