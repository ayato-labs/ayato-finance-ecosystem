import duckdb
from src.core.config import settings

def check_master_codes():
    conn = duckdb.connect(str(settings.JP_MASTER_DB_PATH), read_only=True)
    df = conn.execute("SELECT code, name FROM tickers LIMIT 10").df()
    print(df.to_string())
    # Count 4-digit vs 5-digit codes
    c4 = conn.execute("SELECT COUNT(*) FROM tickers WHERE length(code) = 4").fetchone()[0]
    c5 = conn.execute("SELECT COUNT(*) FROM tickers WHERE length(code) = 5").fetchone()[0]
    print(f"\n4-digit codes: {c4}")
    print(f"5-digit codes: {c5}")
    conn.close()

if __name__ == "__main__":
    check_master_codes()
