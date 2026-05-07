import duckdb
from datetime import datetime
from pathlib import Path

class MasterDBClient:
    def __init__(self):
        # パスは環境に合わせて調整が必要だが、一旦絶対パスで参照
        self.master_db_path = Path("C:/Users/saiha/My_Service/programing/finance/services/master_db/data/master.duckdb")

    def register_provider(self, provider_id: str, db_path: str, version: str, record_count: int):
        conn = duckdb.connect(str(self.master_db_path))
        conn.execute("""
            INSERT OR REPLACE INTO providers (provider_id, db_path, version, last_sync_timestamp, record_count)
            VALUES (?, ?, ?, ?, ?)
        """, (provider_id, db_path, version, datetime.now(), record_count))
        conn.close()
