import duckdb
from pathlib import Path

def init_master_db():
    db_path = Path("master_db/data/master.duckdb")
    conn = duckdb.connect(str(db_path))
    
    # Providers Metadata
    conn.execute("""
        CREATE TABLE IF NOT EXISTS providers (
            provider_id VARCHAR PRIMARY KEY,
            db_path VARCHAR,
            version VARCHAR,
            last_sync_timestamp TIMESTAMP,
            record_count INTEGER
        )
    """)
    
    # Schema Registry (Schema-as-Code)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_registry (
            provider_id VARCHAR,
            table_name VARCHAR,
            column_name VARCHAR,
            data_type VARCHAR,
            is_nullable BOOLEAN,
            contract_definition VARCHAR,
            PRIMARY KEY (provider_id, table_name, column_name)
        )
    """)
    conn.close()

if __name__ == "__main__":
    init_master_db()
