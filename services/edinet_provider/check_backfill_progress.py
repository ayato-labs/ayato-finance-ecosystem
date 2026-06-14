import datetime
from src.datalake.shared.infra.db import db_manager

def check_progress():
    total_period_days = 1825  # 5 years
    try:
        with db_manager.connect_master(read_only=True) as conn:
            # Get completed and failed counts
            completed = conn.execute("SELECT count(*) FROM ingestion_progress WHERE status = 'completed'").fetchone()[0]
            failed = conn.execute("SELECT count(*) FROM ingestion_progress WHERE status = 'failed'").fetchone()[0]
            
            # Get the rate from the last hour
            hour_ago = datetime.datetime.now() - datetime.timedelta(hours=1)
            recently_completed = conn.execute(
                "SELECT count(*) FROM ingestion_progress WHERE status = 'completed' AND updated_at > ?",
                [hour_ago]
            ).fetchone()[0]
            
            # Get latest processing date
            latest_date_row = conn.execute("SELECT max(target_date) FROM ingestion_progress WHERE status = 'completed'").fetchone()
            latest_date = latest_date_row[0] if latest_date_row else "None"

            print(f"COMPLETED={completed}")
            print(f"FAILED={failed}")
            print(f"TOTAL_DAYS={total_period_days}")
            print(f"RATE_PER_HOUR={recently_completed}")
            print(f"LATEST_PROCESSED_DATE={latest_date}")
    except Exception as e:
        print(f"ERROR={e}")

if __name__ == "__main__":
    check_progress()
