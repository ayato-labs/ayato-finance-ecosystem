import threading

import duckdb

conn1 = duckdb.connect("main.duckdb")
conn1.execute("ATTACH 'attached.duckdb' AS a (READ_ONLY)")


def worker():
    try:
        conn2 = duckdb.connect("attached.duckdb")
        print("Worker connected to attached.duckdb for writing")
    except Exception as e:
        print(f"Worker failed: {e}")


t = threading.Thread(target=worker)
t.start()
t.join()
