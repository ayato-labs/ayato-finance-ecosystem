import sqlite3
import json
from pathlib import Path

def audit_quality():
    db_path = Path("data/sync_master.sqlite")
    if not db_path.exists():
        print("Master DB not found.")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # 日本株と米国株からそれぞれサンプルを取得
    samples = []
    for market in ['jp', 'us']:
        rows = conn.execute("""
            SELECT ticker, accession_number, market, result_json 
            FROM jobs 
            WHERE status = 'COMPLETED' AND market = ?
            ORDER BY updated_at DESC 
            LIMIT 2
        """, (market,)).fetchall()
        samples.extend(rows)
    
    print(f"--- Quality Audit Report (Sample size: {len(samples)}) ---\n")
    
    for job in samples:
        print(f"TARGET: {job['ticker']} ({job['market']}) | {job['accession_number']}")
        if not job['result_json']:
            print("  [ERROR] No result_json found despite COMPLETED status.")
            continue
            
        try:
            data = json.loads(job['result_json'])
            thinking = data.get("thinking", "N/A")
            facts = data.get("facts", [])
            
            print(f"  [Thinking]: {thinking[:300]}...")
            print(f"  [Facts Found]: {len(facts)}")
            
            # 数値が含まれているかチェック
            num_with_numbers = sum(1 for f in facts if any(c.isdigit() for c in str(f.get('content', ''))))
            print(f"  [Facts with Numbers]: {num_with_numbers}/{len(facts)}")
            
            for i, f in enumerate(facts[:2]): # 最初の2つを表示
                cat = f.get('category', 'N/A')
                content = f.get('content', 'N/A')
                impact = f.get('impact', 'N/A')
                print(f"    - [{cat}]: {content[:150]} (Impact: {impact})")
                
        except Exception as e:
            print(f"  [ERROR] Failed to parse JSON: {e}")
        
        print("-" * 40)

    # 失敗件数の詳細確認
    failed = conn.execute("SELECT error_message FROM jobs WHERE status = 'FAILED'").fetchall()
    if failed:
        print(f"\n--- Failure Analysis ({len(failed)} cases) ---")
        for f in failed:
            print(f"  Reason: {f[0]}")

    conn.close()

if __name__ == "__main__":
    audit_quality()
