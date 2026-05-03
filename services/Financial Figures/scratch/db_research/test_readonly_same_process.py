import threading

import duckdb

# Main thread API connection
conn1 = duckdb.connect("main.duckdb", read_only=True)
conn1.execute("ATTACH 'attached.duckdb' AS a (READ_ONLY)")


def worker():
    try:
        # Background thread sync connection
        conn2 = duckdb.connect("attached.duckdb", read_only=False)
        conn2.execute("CREATE TABLE IF NOT EXISTS test (id INT)")
        print("Worker connected to attached.duckdb for writing")
    except Exception as e:
        print(f"Worker failed: {e}")


t = threading.Thread(target=worker)
t.start()
t.join()
