import duckdb

def main():
    shards = {
        "master": "data/edinet_master.duckdb",
        "registry_db": "data/edinet_registry.duckdb",
        "facts_db": "data/edinet_facts.duckdb",
        "narr_db": "data/edinet_narratives.duckdb"
    }
    
    print("# Database Schema Map (Quad-Split)\n")
    
    for alias, path in shards.items():
        print(f"## Shard: {alias} ({path})")
        try:
            conn = duckdb.connect(path)
            # Use 'SHOW ALL TABLES' to see what's in there
            tables = conn.execute("SHOW TABLES").fetchall()
            if not tables:
                print("*No tables found in this shard.*")
            
            for (tname,) in tables:
                print(f"### Table: {tname}")
                print("| Column | Type | Constraints |")
                print("| --- | --- | --- |")
                cols = conn.execute(f"DESCRIBE {tname}").fetchall()
                for c in cols:
                    name, type_, null, pk, def_, extra = c
                    constraints = []
                    if pk == 'PRI':
                        constraints.append("PRIMARY KEY")
                    if null == 'NO':
                        constraints.append("NOT NULL")
                    if def_:
                        constraints.append(f"DEFAULT {def_}")
                    print(f"| {name} | {type_} | {', '.join(constraints)} |")
                print()
            conn.close()
        except Exception as e:
            print(f"*Error accessing shard: {e}*")

if __name__ == "__main__":
    main()
