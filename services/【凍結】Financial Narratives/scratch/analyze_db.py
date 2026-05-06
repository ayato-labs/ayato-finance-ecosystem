import duckdb
import json
from pathlib import Path

paths = [
    "data/financial_narratives.duckdb",
    "finance_narratives.duckdb",
    "data/finance_narratives.duckdb"
]
db_path = None
for p in paths:
    if Path(p).exists():
        db_path = p
        break

if not db_path:
    print(f"Error: Database file not found in {paths}.")
    exit(1)

print(f"Analyzing database at: {db_path}")

with duckdb.connect(db_path) as conn:
    # テーブル一覧を取得
    tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
    print(f"Available Tables: {tables}")

    # 1. 全体の統計
    total_filings = 0
    if "filings" in tables:
        total_filings = conn.execute("SELECT COUNT(*) FROM filings").fetchone()[0]
    
    total_structurings = 0
    # テーブル名が異なる可能性を考慮 (structured_facts など)
    struct_table = "structuring" if "structuring" in tables else ("structured_facts" if "structured_facts" in tables else None)
    
    if struct_table:
        total_structurings = conn.execute(f"SELECT COUNT(*) FROM {struct_table}").fetchone()[0]
    
    print(f"--- Global Statistics ---")
    print(f"Total Filings: {total_filings}")
    print(f"Total Structured Records: {total_structurings}")
    
    # 2. 銘柄別(Ticker)の分布 (Top 10)
    print(f"\n--- Top 10 Tickers by Filing Count ---")
    tickers = conn.execute("""
        SELECT ticker, COUNT(*) as count 
        FROM filings 
        GROUP BY ticker 
        ORDER BY count DESC 
        LIMIT 10
    """).fetchall()
    for t, c in tickers:
        print(f"{t}: {c}")
        
    # 3. フォーム別(Form)の分布
    print(f"\n--- Distribution by Form Type ---")
    forms = conn.execute("""
        SELECT form, COUNT(*) as count 
        FROM filings 
        GROUP BY form 
        ORDER BY count DESC
    """).fetchall()
    for f, c in forms:
        print(f"{f}: {c}")

    # 4. 直近の取得データ (Top 5)
    print(f"\n--- Most Recent Filings ---")
    recent = conn.execute("""
        SELECT ticker, form, filing_date, accession_number 
        FROM filings 
        ORDER BY filing_date DESC 
        LIMIT 5
    """).fetchall()
    for t, f, d, a in recent:
        print(f"{d} | {t} | {f} | {a}")

    # 5. 構造化データのサンプル (もしあれば)
    if total_structurings > 0 and struct_table:
        print(f"\n--- Sample Structured Data (First Record) ---")
        sample = conn.execute(f"SELECT ticker, structured_data FROM {struct_table} LIMIT 1").fetchone()
        if sample:
            print(f"Ticker: {sample[0]}")
            # Pretty print JSON
            data = json.loads(sample[1])
            print(json.dumps(data, indent=2, ensure_ascii=False))
