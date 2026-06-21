import duckdb
con = duckdb.connect('data/yfinance.duckdb')
tables = con.execute("SHOW TABLES").fetchall()
print(f"Tables: {tables}")
