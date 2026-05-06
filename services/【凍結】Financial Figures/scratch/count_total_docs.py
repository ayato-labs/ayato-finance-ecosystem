import duckdb
con = duckdb.connect("data/audit/edinet_raw.duckdb")
res = con.execute("SELECT COUNT(*) FROM documents").fetchone()
print(f"Total Documents in RAW: {res[0]}")
con.close()
