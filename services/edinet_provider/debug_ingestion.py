import sys
from pathlib import Path

# Add current dir to path
sys.path.append(str(Path.cwd()))

print("--- DEBUG START ---")
try:
    print("Importing settings...")
    from src.infra.config import settings

    print(f"Master DB Path: {settings.MASTER_DB_PATH}")

    print("Importing db_manager...")
    from src.infra.db import db_manager

    print("Attempting to connect to Master DB...")
    with db_manager.connect_master() as conn:
        print("Connected!")
        res = conn.execute(
            "SELECT name FROM registry_db.sqlite_master WHERE type='table'"
        ).fetchall()
        print(f"Tables in registry_db: {res}")

    print("Importing DataIngestor...")
    from src.service.ingestor import DataIngestor

    print("Initializing DataIngestor...")
    ingestor = DataIngestor()
    print("Success!")

except Exception as e:
    print(f"FAILED: {e}")
    import traceback

    traceback.print_exc()

print("--- DEBUG END ---")
