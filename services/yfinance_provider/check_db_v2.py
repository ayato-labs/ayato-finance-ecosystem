import duckdb

con = duckdb.connect(r"C:\Users\saiha\My_Service\programing\finance\data\yfinance\yfinance.duckdb")
result = con.execute(
    "SELECT count(distinct ticker) FROM prices WHERE ticker NOT LIKE '%.T%'"
).fetchone()
print(f"Ticker count: {result[0]}")
