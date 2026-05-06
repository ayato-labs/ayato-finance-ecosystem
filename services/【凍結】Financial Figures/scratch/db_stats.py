import duckdb
from pathlib import Path
import json

db_configs = {
    "JP Market": "data/markets/jp.duckdb",
    "EDINET Statutory": "data/edinet.duckdb",
    "US Market": "data/markets/us.duckdb",
    "Traceability & Audit": "data/audit/traceability.duckdb"
}

table_map = {
    "JP Market": ["tickers", "company_facts"],
    "EDINET Statutory": ["documents", "raw_facts", "company_facts"],
    "US Market": ["tickers", "company_facts"],
    "Traceability & Audit": ["sync_sessions", "mapping_audit", "sync_progress"]
}

def get_stats():
    stats = {}
    for shard, db_path in db_configs.items():
        full_path = Path(db_path)
        if not full_path.exists():
            stats[shard] = {"status": "Not Found", "path": str(full_path)}
            continue
        
        try:
            conn = duckdb.connect(str(full_path), read_only=True)
            shard_stats = {"status": "Active", "size_mb": round(full_path.stat().st_size / (1024 * 1024), 2)}
            
            # List all tables to see if they match schema
            existing_tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
            shard_stats["tables"] = {}
            
            for table in table_map.get(shard, []):
                if table in existing_tables:
                    count = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                    shard_stats["tables"][table] = count
                else:
                    shard_stats["tables"][table] = "Table Not Found"
            
            # Check for any other tables not in table_map
            extra_tables = [t for t in existing_tables if t not in table_map.get(shard, [])]
            if extra_tables:
                shard_stats["extra_tables"] = {}
                for t in extra_tables:
                    try:
                        count = conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                        shard_stats["extra_tables"][t] = count
                    except:
                        shard_stats["extra_tables"][t] = "Error"
                        
            stats[shard] = shard_stats
            conn.close()
        except Exception as e:
            stats[shard] = {"status": "Error", "message": str(e)}
            
    return stats

if __name__ == "__main__":
    results = get_stats()
    print(json.dumps(results, indent=2, ensure_ascii=False))
