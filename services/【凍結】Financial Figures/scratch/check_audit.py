from src.core.db import db_manager
from src.core.config import settings
import os

path = os.path.join(settings.DATA_DIR, "audit", "traceability.duckdb")
with db_manager.connect(path, read_only=True) as conn:
    count = conn.execute("SELECT COUNT(*) FROM mapping_audit").fetchone()[0]
    print(f"Mapping Audit Count: {count}")
    
    # Also check recent sessions
    sessions = conn.execute("SELECT session_id, status, started_at FROM sync_sessions ORDER BY started_at DESC LIMIT 5").fetchall()
    print("\nRecent Sessions:")
    for s in sessions:
        print(s)
