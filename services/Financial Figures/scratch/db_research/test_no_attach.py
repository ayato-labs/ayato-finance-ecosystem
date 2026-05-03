import threading

import duckdb

conn_us_main = duckdb.connect("us.duckdb")
conn_jp_main = duckdb.connect("jp.duckdb")


def worker():
    try:
        conn_jp_worker = duckdb.connect("jp.duckdb")
        conn_jp_worker.execute("CREATE TABLE IF NOT EXISTS test (id INT)")
        print("Worker connected to jp.duckdb for writing")
    except Exception as e:
        print(f"Worker failed: {e}")


t = threading.Thread(target=worker)
t.start()
t.join()
