import pandas as pd
import duckdb
from decimal import Decimal

# Create a dataframe with small decimals first, then a huge one
data = []
for i in range(1000): # DuckDB sample size is typically around 1000
    data.append({"TurnoverValue": Decimal("100.5")})

data.append({"TurnoverValue": Decimal("158609607470.0")})

df = pd.DataFrame(data)

conn = duckdb.connect()
conn.register("source_df", df)

try:
    print("Executing SELECT * FROM source_df...")
    conn.execute("SELECT * FROM source_df").fetchall()
    print("Success!")
except Exception as e:
    print(f"Error reading DataFrame: {e}")
