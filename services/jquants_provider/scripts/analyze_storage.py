import duckdb
import pandas as pd
from pathlib import Path

def analyze_storage():
    db_path = "data/jquants.duckdb"
    if not Path(db_path).exists():
        print("Database not found.")
        return

    conn = duckdb.connect(db_path)
    tables = ["daily_prices", "company_facts", "tickers"]
    
    print(f"=== Storage Efficiency Analysis: {db_path} ===")
    
    for table in tables:
        try:
            print(f"\n[Table: {table}]")
            # Get columns and types
            cols = conn.execute(f"PRAGMA table_info('{table}')").df()
            total_rows = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            print(f"Total Rows: {total_rows}")
            
            # Analyze each column
            results = []
            for _, row in cols.iterrows():
                col_name = row['name']
                col_type = row['type']
                
                # Check for nulls and cardinality
                stats = conn.execute(f"""
                    SELECT 
                        count(DISTINCT "{col_name}") as unique_vals,
                        count(*) FILTER (WHERE "{col_name}" IS NULL) as null_count
                    FROM {table}
                """).fetchone()
                
                results.append({
                    "Column": col_name,
                    "Type": col_type,
                    "Unique": stats[0],
                    "Nulls": stats[1],
                    "Entropy": round(stats[0] / total_rows * 100, 2) if total_rows > 0 else 0
                })
            
            print(pd.DataFrame(results))
        except Exception as e:
            print(f"Could not analyze {table}: {e}")
            
    conn.close()

if __name__ == "__main__":
    analyze_storage()
