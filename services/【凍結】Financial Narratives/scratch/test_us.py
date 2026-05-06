import duckdb
import json

with duckdb.connect('data/narratives_us.duckdb') as conn:
    res = conn.execute("SELECT sections FROM filings WHERE accession_number = '0001950047-26-003721'").fetchone()
    if res:
        parsed = json.loads(res[0])
        print(f"Keys: {list(parsed.keys())}")
        print(f"Content length: {len(str(parsed))}")
