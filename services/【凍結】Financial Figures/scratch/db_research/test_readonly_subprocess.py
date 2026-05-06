import subprocess
import sys

import duckdb

conn1 = duckdb.connect("main.duckdb")
conn1.execute("ATTACH 'attached.duckdb' AS a (READ_ONLY)")

# Try to write to attached.duckdb from another process
cmd = 'import duckdb; conn = duckdb.connect("attached.duckdb"); conn.execute("CREATE TABLE IF NOT EXISTS test (id INT)"); print("Subprocess success")'
try:
    output = subprocess.check_output([sys.executable, "-c", cmd], stderr=subprocess.STDOUT)
    print(output.decode("utf-8"))
except subprocess.CalledProcessError as e:
    try:
        print(f"Subprocess failed: {e.output.decode('cp932')}")
    except:
        print(f"Subprocess failed: {e.output}")
