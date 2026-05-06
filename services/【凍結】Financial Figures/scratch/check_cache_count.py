import duckdb
con = duckdb.connect("data/markets/edinet_normalized.duckdb")
count = con.execute("SELECT count(*) FROM tag_mappings").fetchone()[0]
print(f"Cached Mappings: {count}")
con.close()
