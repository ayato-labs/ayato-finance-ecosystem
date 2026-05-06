import sqlite3

def reset():
    conn = sqlite3.connect('data/sync_master.sqlite')
    cursor = conn.cursor()
    cursor.execute("UPDATE jobs SET status = 'PENDING', retry_count = 0 WHERE status = 'FAILED'")
    conn.commit()
    print("Reset complete.")

if __name__ == "__main__":
    reset()
