import duckdb
from src.core.config import settings

def check_continuity():
    conn = duckdb.connect(str(settings.JP_PRICES_DB_PATH), read_only=True)
    # Check Toyota (7203) continuity
    print("Checking continuity for Toyota (7203):")
    df = conn.execute("""
        SELECT Date, Close 
        FROM daily_prices 
        WHERE Code = '7203' 
        ORDER BY Date DESC 
        LIMIT 15
    """).df()
    print(df.to_string())
    conn.close()

if __name__ == "__main__":
    check_continuity()
