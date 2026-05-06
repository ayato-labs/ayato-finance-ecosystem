import duckdb
con = duckdb.connect("data/markets/edinet_normalized.duckdb")
res = con.execute("SHOW TABLES").fetchall()
print(f"Tables: {res}")
con.close()
