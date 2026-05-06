import sqlite3
import json

def audit():
    conn = sqlite3.connect('data/sync_master.sqlite')
    conn.row_factory = sqlite3.Row
    # US市場かつ、空でない結果を持つ最新の2件
    rows = conn.execute("""
        SELECT ticker, result_json 
        FROM jobs 
        WHERE market = 'us' AND status = 'COMPLETED' AND result_json != '{}' AND result_json IS NOT NULL
        ORDER BY updated_at DESC 
        LIMIT 2
    """).fetchall()

    if not rows:
        print("No new US facts found yet. Waiting for workers...")
        return

    for row in rows:
        print(f"=== Ticker: {row['ticker']} ===")
        try:
            data = json.loads(row['result_json'])
            print(f"[Thinking]: {data.get('thinking', 'N/A')[:300]}...")
            facts = data.get('facts', [])
            print(f"[Facts Found]: {len(facts)}")
            for i, f in enumerate(facts[:3]):
                print(f"  {i+1}. {json.dumps(f, ensure_ascii=False)[:250]}...")
        except Exception as e:
            print(f"Error parsing JSON: {e}")
        print("="*50)
    conn.close()

if __name__ == "__main__":
    audit()
