import duckdb
from src.core.config import settings

def verify_ticker(code):
    conn = duckdb.connect(str(settings.JP_PRICES_DB_PATH), read_only=True)
    res = conn.execute(f"SELECT MAX(Date), COUNT(*) FROM daily_prices WHERE Code = '{code}'").fetchone()
    print(f"Ticker {code}: Max Date = {res[0]}, Total Records = {res[1]}")
    conn.close()

if __name__ == "__main__":
    verify_ticker('7203')
    verify_ticker('9984') # Softbank
