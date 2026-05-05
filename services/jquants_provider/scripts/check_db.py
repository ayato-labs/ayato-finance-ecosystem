import duckdb
import pandas as pd
from pathlib import Path

def check_db_stats():
    master_path = Path("data/master.duckdb")
    jquants_path = Path("data/jquants.duckdb")
    
    print("=== Database Status Report ===")
    
    if master_path.exists():
        conn = duckdb.connect(str(master_path))
        print("\n[Catalog Table (master.duckdb)]")
        try:
            df = conn.execute("SELECT * FROM catalog").df()
            print(df if not df.empty else "Catalog is empty.")
        except Exception as e:
            print(f"Error reading catalog: {e}")
        conn.close()
    else:
        print("\nmaster.duckdb does not exist.")

    if jquants_path.exists():
        conn = duckdb.connect(str(jquants_path))
        print("\n[Table Record Counts (jquants.duckdb)]")
        try:
            tables = conn.execute("SHOW TABLES").fetchall()
            for t in tables:
                t_name = t[0]
                if t_name.startswith("__"): continue
                count = conn.execute(f"SELECT count(*) FROM {t_name}").fetchone()[0]
                print(f"- {t_name}: {count} records")
        except Exception as e:
            print(f"Error reading shard: {e}")
        conn.close()
    else:
        print("\njquants.duckdb does not exist.")

if __name__ == "__main__":
    check_db_stats()
