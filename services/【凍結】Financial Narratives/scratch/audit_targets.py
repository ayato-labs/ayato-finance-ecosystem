import sqlite3
import json

def audit():
    conn = sqlite3.connect('data/sync_master.sqlite')
    conn.row_factory = sqlite3.Row
    # AAPL, NVDAの10-K, 10-Qを狙い撃ち
    rows = conn.execute("""
        SELECT ticker, accession_number, result_json 
        FROM jobs 
        WHERE ticker IN ('AAPL', 'NVDA') AND status = 'COMPLETED'
        ORDER BY updated_at DESC
    """).fetchall()

    if not rows:
        print("No completed AAPL/NVDA jobs found yet.")
        return

    for row in rows:
        data = json.loads(row['result_json'])
        facts = data.get('facts', [])
        if facts:
            print(f"=== SUCCESS: {row['ticker']} ({row['accession_number']}) ===")
            print(f"[Facts Found]: {len(facts)}")
            for f in facts[:2]:
                print(f"  - {json.dumps(f, ensure_ascii=False)[:300]}")
            print("="*50)
            break # 1件見つかればOK
    else:
        print("AAPL/NVDA jobs found but all are empty or not processed with new parser yet.")

    conn.close()

if __name__ == "__main__":
    audit()
