import threading
import time

import duckdb

db_path = "test.duckdb"

# Create file
conn1 = duckdb.connect(db_path)
conn1.execute("CREATE TABLE IF NOT EXISTS test (id INT)")


def write_db():
    conn2 = duckdb.connect(db_path)
    for i in range(5):
        conn2.execute("INSERT INTO test VALUES (?)", [i])
        time.sleep(0.1)
    conn2.close()


t = threading.Thread(target=write_db)
t.start()

for _i in range(5):
    res = conn1.execute("SELECT count(*) FROM test").fetchone()
    print(f"Count: {res[0]}")
    time.sleep(0.1)

t.join()
conn1.close()
