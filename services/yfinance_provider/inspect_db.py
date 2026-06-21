import duckdb
con = duckdb.connect(r'C:\Users\saiha\My_Service\programing\finance\data\yfinance\yfinance.duckdb')
tables = con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()
print(f"Tables: {tables}")

for table in tables:
    table_name = table[0]
    count = con.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
    print(f"Table '{table_name}' has {count} rows.")
    
    # Sample data to understand content
    if count > 0:
        sample = con.execute(f"SELECT * FROM {table_name} LIMIT 5").df()
        print(f"Sample from '{table_name}':\n{sample}\n")
