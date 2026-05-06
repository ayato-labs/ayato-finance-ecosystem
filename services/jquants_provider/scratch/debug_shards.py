import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import duckdb
from src.core.config import settings

def check_tables():
    shards = {
        "master": settings.JP_MASTER_DB_PATH,
        "prices": settings.JP_PRICES_DB_PATH,
        "financials": settings.JP_FACTS_DB_PATH,
    }
    
    for name, path in shards.items():
        print(f"\nChecking shard: {name} ({path})")
        try:
            conn = duckdb.connect(str(path))
            tables = conn.execute("SHOW TABLES").fetchall()
            print(f"Tables: {tables}")
            conn.close()
        except Exception as e:
            print(f"Error checking {name}: {e}")

if __name__ == "__main__":
    check_tables()
