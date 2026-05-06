from src.core.db import db_manager
from src.core.config import settings
import os
import json

path = os.path.join(settings.DATA_DIR, "audit", "traceability.duckdb")
with db_manager.connect(path, read_only=True) as conn:
    session = conn.execute("SELECT * FROM sync_sessions WHERE market = 'JP_BACKFILL' ORDER BY started_at DESC LIMIT 1").fetchone()
    if session:
        # Get column names
        cols = [d[0] for d in conn.description]
        session_dict = dict(zip(cols, session))
        print(json.dumps(session_dict, indent=2, default=str))
    else:
        print("No JP_BACKFILL session found.")
