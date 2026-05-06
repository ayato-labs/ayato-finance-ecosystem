from src.core.db import db_manager
from src.core.config import settings
import os

path = os.path.join(settings.DATA_DIR, "markets", "jp.duckdb")
with db_manager.connect(path, read_only=True) as conn:
    dates = conn.execute("SELECT DISTINCT DisclosedDate FROM company_facts ORDER BY DisclosedDate DESC").fetchall()
    print(f"Total Unique Dates: {len(dates)}")
    for d in dates[:20]:
        print(d[0])
