import duckdb

from src.core.config import settings
from src.core.price_resolver import get_safe_price_view_sql


def verify_and_analyze():
    # 1. Setup Database Connections
    conn = duckdb.connect(str(settings.DB_PATH_US))
    conn.execute(f"ATTACH '{settings.DB_PATH_JP}' AS jp")
    audit_db = settings.DATA_DIR / "audit" / "traceability.duckdb"
    conn.execute(f"ATTACH '{audit_db}' AS audit")

    # 2. Define Standardized Financials View
    conn.execute("""
        CREATE OR REPLACE VIEW v_standardized_financials AS
        SELECT 
            'US' as market, t.ticker as symbol, t.name as company_name, 
            m.target_label, f.value, f.unit, f.end_date as period_date, 
            f.fiscal_year, m.reasoning
        FROM main.company_facts f
        JOIN main.tickers t ON f.cik = t.cik
        JOIN audit.mapping_audit m ON m.source_tag = CONCAT('US:', f.tag)
        WHERE m.target_label != 'Other'
        UNION ALL
        SELECT 
            'JP' as market, SUBSTR(t.code, 1, 4) as symbol, t.name as company_name, 
            m.target_label, f.value, f.unit, f.disclosed_date as period_date, 
            f.fiscal_year, m.reasoning
        FROM jp.company_facts f
        JOIN jp.tickers t ON f.code = t.code
        JOIN audit.mapping_audit m ON m.source_tag = CONCAT('JP:', f.tag)
        WHERE m.target_label != 'Other'
    """)

    # 3. Setup Normalized Price View
    price_parquet_path = "C:/Users/saiha/My_Service/programing/finance/daily_stock_price/data/market_data/year=2026/month=04/*.parquet"
    conn.execute(get_safe_price_view_sql(price_parquet_path))

    # Target Tickers
    targets = [{"symbol": "XOM", "market": "US"}, {"symbol": "1301", "market": "JP"}]

    print("\n" + "=" * 85)
    print(
        f"{'Market':<6} | {'Symbol':<8} | {'Margin':<12} | {'PER':<8} | {'Price':<10} | {'Period'}"
    )
    print("-" * 85)

    for target in targets:
        symbol = target["symbol"]

        # Get Financials
        df_fin = conn.execute(
            """
            SELECT target_label, value, period_date, unit
            FROM v_standardized_financials
            WHERE symbol = ?
            ORDER BY period_date DESC
        """,
            [symbol],
        ).df()

        if df_fin.empty:
            print(
                f"{target['market']:<6} | {symbol:<8} | {'No Data':<12} | {'N/A':<8} | {'N/A':<10} | N/A"
            )
            continue

        # Extract latest metrics
        latest_date = df_fin["period_date"].max()
        df_latest = df_fin[df_fin["period_date"] == latest_date]

        def get_val(lbl):
            rows = df_latest[df_latest["target_label"] == lbl]
            return rows["value"].iloc[0] if not rows.empty else None

        sales = get_val("NetSales")
        op_profit = get_val("OperatingProfit")
        net_income = get_val("NetProfit") or get_val("NetIncome")
        eps = get_val("EPS")

        # Calculate Margin
        margin_str = "N/A"
        if sales and op_profit:
            margin_str = f"{op_profit / sales * 100:.2f}%"
        elif sales and net_income:
            margin_str = f"{net_income / sales * 100:.2f}% (Net)"

        # Get Latest Price from Normalized View
        price_query_sym = symbol if target["market"] == "US" else f"{symbol}.T"
        latest_price = None
        try:
            price_df = conn.execute(
                """
                SELECT close FROM v_safe_prices 
                WHERE ticker = ? 
                ORDER BY date DESC LIMIT 1
            """,
                [price_query_sym],
            ).df()
            if not price_df.empty:
                latest_price = price_df["close"].iloc[0]
        except Exception as e:
            print(f"  -> Price Fetch Error for {symbol}: {e}")

        # Calculate PER
        per = "N/A"
        if latest_price and eps and eps > 0:
            per = f"{latest_price / eps:.2f}"

        price_str = f"{latest_price:.2f}" if latest_price is not None else "N/A"
        period_str = str(latest_date).split(" ")[0]

        print(
            f"{target['market']:<6} | {symbol:<8} | {margin_str:<12} | {per:<8} | {price_str:<10} | {period_str}"
        )

    print("=" * 85 + "\n")


if __name__ == "__main__":
    verify_and_analyze()
