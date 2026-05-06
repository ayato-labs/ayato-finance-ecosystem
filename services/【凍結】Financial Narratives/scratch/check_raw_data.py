import sqlite3
import json

def check():
    conn = sqlite3.connect('data/sync_master.sqlite')
    row = conn.execute("SELECT ticker, result_json FROM jobs WHERE status = 'COMPLETED' AND ticker NOT IN ('9999', 'E2E') ORDER BY updated_at DESC LIMIT 1").fetchone()
    if row:
        print(f"Ticker: {row[0]}")
        print("-" * 20)
        print(row[1])
    else:
        print("No non-test COMPLETED jobs found.")
    conn.close()

if __name__ == "__main__":
    check()
