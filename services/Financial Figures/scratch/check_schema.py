import duckdb

db_path = r"C:\Users\saiha\My_Service\programing\finance\Financial Figures\data\markets\us.duckdb"
conn = duckdb.connect(db_path, read_only=True)
print(conn.execute("DESCRIBE company_facts").fetchall())
conn.close()
