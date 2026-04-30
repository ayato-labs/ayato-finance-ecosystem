from pathlib import Path

import duckdb

DB_PATH = Path("data/markets/us.duckdb")


def analyze_storage():
    # We need to run this on a separate connection, but since the sync is running,
    # we might have to wait or use a copy.
    # To avoid WinError 32, we'll try to use the 'read_only=True' again but maybe
    # the sync process is being more aggressive with locks now.

    try:
        conn = duckdb.connect(str(DB_PATH), read_only=True)

        print("--- Column-level Compression Stats ---")
        # This PRAGMA shows compression type and segment info
        res = conn.execute("PRAGMA storage_info('company_facts')").fetchall()

        # Columns of interest: cik, taxonomy, tag, value, end_date
        # Col 0: table_id, 1: column_id, 2: column_name, 3: segment_id, 4: compression, 5: stats...

        stats_map = {}
        for row in res:
            col_name = row[2]
            compression = row[4]
            if col_name not in stats_map:
                stats_map[col_name] = set()
            stats_map[col_name].add(compression)

        for col, algs in stats_map.items():
            print(f"Col {col:15}: {', '.join(algs)}")

    except Exception as e:
        print(f"Analysis failed: {e}")


if __name__ == "__main__":
    analyze_storage()
