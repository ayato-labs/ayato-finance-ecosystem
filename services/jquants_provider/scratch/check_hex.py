import duckdb
from pathlib import Path

db_path = Path("data/jquants.duckdb")

def verify_hex():
    if not db_path.exists():
        return
    conn = duckdb.connect(str(db_path))
    res = conn.execute("SELECT name FROM tickers WHERE code LIKE '7203%'").fetchone()
    if res:
        name = res[0]
        print(f"Name Hex: {name.encode('utf-8').hex()}")
        # Check if it looks like Toyota (トヨタ自動車 in UTF-8: e38388e383aae382bfe887aae58b95e8bb8a)
    conn.close()

if __name__ == "__main__":
    verify_hex()
