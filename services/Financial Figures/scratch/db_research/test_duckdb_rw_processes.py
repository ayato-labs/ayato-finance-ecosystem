import subprocess
import sys
import time

import duckdb


# Process A: Write connection
def writer_process():
    code = """
import duckdb
import time
conn = duckdb.connect("test_lock.duckdb", read_only=False)
conn.execute("CREATE TABLE IF NOT EXISTS test (id INT)")
print("Writer has lock")
time.sleep(5)
conn.close()
"""
    return subprocess.Popen([sys.executable, "-c", code])


# Process B: Read connection
def reader_process():
    code = """
import duckdb
try:
    conn = duckdb.connect("test_lock.duckdb", read_only=True)
    print("Reader got lock")
    conn.close()
except Exception as e:
    print(f"Reader failed: {e}")
"""
    subprocess.run([sys.executable, "-c", code])


if __name__ == "__main__":
    # Initialize db
    duckdb.connect("test_lock.duckdb").close()

    p = writer_process()
    time.sleep(2)  # let writer get lock
    reader_process()
    p.wait()
