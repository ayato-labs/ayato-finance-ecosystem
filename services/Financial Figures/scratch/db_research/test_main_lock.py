import duckdb

try:
    conn1 = duckdb.connect("main.duckdb")
    print("conn1 ok")
    conn2 = duckdb.connect("main.duckdb")
    print("conn2 ok")
except Exception as e:
    print(f"Error: {e}")
