import duckdb
import pandas as pd

def audit_data():
    conn = duckdb.connect('data/markets/jp.duckdb')
    
    print("=== Data Audit Report ===")
    
    # 1. ソース別の件数
    print("\n[1] Records by Source (session_id prefix):")
    sources = conn.execute("""
        SELECT 
            CASE 
                WHEN session_id LIKE 'edinet%' THEN 'EDINET'
                WHEN session_id LIKE 'JP_BACKFILL%' THEN 'J-Quants Backfill'
                ELSE 'Other'
            END as source,
            count(*) as count
        FROM company_facts
        GROUP BY 1
    """).df()
    print(sources)
    
    # 2. EDINETデータの品質（NULL率）
    print("\n[2] EDINET Data Quality (NULL rates for key items):")
    quality = conn.execute("""
        SELECT 
            count(*) as total_docs,
            count(NetSales) as with_sales,
            count(OperatingProfit) as with_op,
            count(Profit) as with_profit,
            round(count(NetSales) * 100.0 / count(*), 1) as sales_fill_rate_pct
        FROM company_facts
        WHERE session_id LIKE 'edinet%'
    """).df()
    print(quality)
    
    # 3. 実際の値のサンプル（EDINET）
    print("\n[3] EDINET Sample Values (Normalized):")
    samples = conn.execute("""
        SELECT DisclosedDate, LocalCode, NetSales, Profit
        FROM company_facts
        WHERE session_id LIKE 'edinet%'
          AND NetSales IS NOT NULL
        LIMIT 5
    """).df()
    print(samples)
    
    conn.close()

if __name__ == "__main__":
    audit_data()
