import duckdb
from pathlib import Path

db_path = Path("data/jquants.duckdb")

def verify_encoding():
    if not db_path.exists():
        return
    conn = duckdb.connect(str(db_path))
    # Toyota Code in J-Quants is usually 72030 (with extra digit)
    res = conn.execute("SELECT name FROM tickers WHERE code LIKE '7203%'").fetchone()
    if res:
        print(f"Code 7203 Name: {res[0]}")
    else:
        print("Ticker 7203 not found.")
    conn.close()

if __name__ == "__main__":
    verify_encoding()
