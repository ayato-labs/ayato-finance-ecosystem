import duckdb
from src.core.config import settings

def check_stats():
    try:
        conn = duckdb.connect(str(settings.DB_PATH_EDINET_NORM), read_only=True)
        facts_count = conn.execute("SELECT count(*) FROM company_facts").fetchone()[0]
        docs_count = conn.execute("SELECT count(distinct accession_number) FROM company_facts").fetchone()[0]
        print(f"Normalized Facts: {facts_count}")
        print(f"Unique Documents: {docs_count}")
    except Exception as e:
        print(f"Error checking stats: {e}")

if __name__ == "__main__":
    check_stats()
