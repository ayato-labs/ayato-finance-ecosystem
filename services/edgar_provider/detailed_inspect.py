import duckdb
import json

db_path = r"C:\Users\saiha\My_Service\programing\data\edgar\edgar.duckdb"
conn = duckdb.connect(db_path, read_only=True)

print("=== filings schema ===")
print(conn.execute("PRAGMA table_info('filings')").fetchall())

print("\n=== filings count ===")
print("COUNT:", conn.execute("SELECT COUNT(*) FROM filings").fetchone())

print("\n=== sample data check ===")
row = conn.execute("SELECT ticker, form, sections FROM filings LIMIT 1").fetchone()
if row:
    ticker, form, sections_json = row
    print(f"Ticker: {ticker}, Form: {form}")
    if isinstance(sections_json, str):
        sections = json.loads(sections_json)
    else:
        sections = sections_json
    print("Sections keys:", list(sections.keys()) if sections else "None")
    for k, v in (sections or {}).items():
        print(f"  Section: {k} | Length: {len(v) if v else 0}")
        if v:
            print("  Snippet:", v[:200].replace("\n", " "))
else:
    print("No data found in filings table.")

conn.close()
