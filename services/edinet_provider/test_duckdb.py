import duckdb
import os

db_path = r"C:\Users\saiha\My_Service\programing\finance\services\edinet_provider\data\edinet_master.duckdb"
print(f"Connecting to {db_path}...")
try:
    conn = duckdb.connect(db_path)
    print("Connected successfully!")
    print(conn.execute("SELECT * FROM sqlite_master").fetchall())
    conn.close()
except Exception as e:
    print(f"Error: {e}")
