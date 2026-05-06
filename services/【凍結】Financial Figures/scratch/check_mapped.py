import duckdb
import pandas as pd

def check_mapped_data():
    conn = duckdb.connect('data/edinet.duckdb')
    
    print("=== EDINET AI-Mapped Data Check ===")
    
    # 実際にAIがマッピングした項目の統計
    print("\n[1] Top Mapped Labels:")
    labels = conn.execute("""
        SELECT label, count(*) as count 
        FROM company_facts 
        GROUP BY 1 
        ORDER BY 2 DESC 
        LIMIT 10
    """).df()
    print(labels)
    
    # 具体的な数値データのサンプル
    print("\n[2] Sample Mapped Values (NetSales / Profit):")
    samples = conn.execute("""
        SELECT 
            disclosed_date, 
            code, 
            label, 
            value,
            ingested_at
        FROM company_facts 
        WHERE label IN ('NetSales', 'Profit', 'OperatingProfit')
        ORDER BY ingested_at DESC 
        LIMIT 10
    """).df()
    print(samples)
    
    conn.close()

if __name__ == "__main__":
    check_mapped_data()
