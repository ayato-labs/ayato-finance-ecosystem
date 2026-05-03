import duckdb


def check_tickers():
    price_parquet_path = "C:/Users/saiha/My_Service/programing/finance/daily_stock_price/data/market_data/year=2026/month=04/*.parquet"
    conn = duckdb.connect(":memory:")

    # Check for JP and US patterns
    print("JP Samples:")
    print(
        conn.execute(
            f"SELECT DISTINCT ticker FROM '{price_parquet_path}' WHERE ticker LIKE '1301%' LIMIT 5"
        ).fetchall()
    )

    print("\nUS Samples:")
    print(
        conn.execute(
            f"SELECT DISTINCT ticker FROM '{price_parquet_path}' WHERE ticker LIKE 'XOM%' LIMIT 5"
        ).fetchall()
    )


if __name__ == "__main__":
    check_tickers()
