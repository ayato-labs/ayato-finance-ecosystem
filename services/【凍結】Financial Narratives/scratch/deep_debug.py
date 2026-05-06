import sqlite3
import json

def debug():
    conn = sqlite3.connect('data/sync_master.sqlite')
    conn.row_factory = sqlite3.Row
    row = conn.execute("""
        SELECT ticker, result_json 
        FROM jobs 
        WHERE market = 'us' AND status = 'COMPLETED'
        ORDER BY updated_at DESC 
        LIMIT 1
    """).fetchone()

    if row:
        print(f"=== DEBUG: {row['ticker']} ===")
        data = json.loads(row['result_json'])
        print("--- Thinking ---")
        print(data.get('thinking', 'N/A'))
        print("--- Facts ---")
        print(json.dumps(data.get('facts', []), indent=2, ensure_ascii=False))
        
        # セクションが正しく渡されているか、Data Lake側も確認
        import duckdb
        dk_conn = duckdb.connect('data/narratives_us.duckdb', read_only=True)
        acc_no = conn.execute("SELECT accession_number FROM jobs WHERE ticker = ? ORDER BY updated_at DESC LIMIT 1", (row['ticker'],)).fetchone()[0]
        sections_raw = dk_conn.execute("SELECT sections FROM filings WHERE accession_number = ?", (acc_no,)).fetchone()
        if sections_raw:
            print(f"--- Data Lake Sections Found ---")
            # 簡易的にキーだけ
            from src.storage import FinancialNarrativeStorage
            storage = FinancialNarrativeStorage('data/narratives_us.duckdb')
            sections = storage.get_sections(acc_no)
            print(f"Keys: {list(sections.keys())}")
        dk_conn.close()

    conn.close()

if __name__ == "__main__":
    debug()
