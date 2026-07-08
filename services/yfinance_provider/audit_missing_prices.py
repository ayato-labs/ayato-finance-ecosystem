import duckdb

# データベースに接続
db_path = r"C:\Users\saiha\My_Service\programing\finance\data\yfinance\yfinance.duckdb"
con = duckdb.connect(db_path)

# SQLクエリをより安全に記述するためにヒアドキュメントを使用せず、文字列として連結
query = (
    "SELECT tm.ticker, count(p.ticker) as price_count, count(f.ticker) as fin_count "
    "FROM ticker_master AS tm "
    "LEFT JOIN prices AS p ON tm.ticker = p.ticker "
    "LEFT JOIN financials AS f ON tm.ticker = f.ticker "
    "GROUP BY tm.ticker "
    "HAVING fin_count > 0 AND price_count < 5"
)

# クエリを実行
try:
    result = con.execute(query).df()
    print("Found tickers with missing price data:")
    print(result)

    # リストに保存 (必要に応じて)
    tickers_to_retry = result["ticker"].tolist()
    print(f"\nTotal tickers to retry: {len(tickers_to_retry)}")

except Exception as e:
    print(f"Error executing query: {e}")
finally:
    con.close()
