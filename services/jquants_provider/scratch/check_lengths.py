import duckdb
from src.core.config import settings

def check_lengths():
    conn = duckdb.connect(str(settings.JP_PRICES_DB_PATH), read_only=True)
    df = conn.execute("SELECT length(Code) as len, COUNT(*) as count FROM daily_prices GROUP BY len").df()
    print(df.to_string())
    
    print("\nSample 4-digit codes if any:")
    df4 = conn.execute("SELECT DISTINCT Code FROM daily_prices WHERE length(Code) = 4 LIMIT 5").df()
    print(df4.to_string())

    print("\nSample 5-digit codes if any:")
    df5 = conn.execute("SELECT DISTINCT Code FROM daily_prices WHERE length(Code) = 5 LIMIT 5").df()
    print(df5.to_string())
    
    conn.close()

if __name__ == "__main__":
    check_lengths()
