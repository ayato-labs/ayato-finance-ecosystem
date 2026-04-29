import duckdb

from src.core.config import settings


def upgrade_mappings():
    db_path = settings.DATA_DIR / "audit" / "traceability.duckdb"
    print(f"Connecting to audit DB: {db_path}")

    with duckdb.connect(str(db_path)) as conn:
        # 1. Count current 'Other' mappings matching keywords
        q_count = """
        SELECT count(*) FROM mapping_audit 
        WHERE target_label = 'Other' 
          AND (source_tag ILIKE '%Research%' 
               OR source_tag ILIKE '%Development%' 
               OR source_tag ILIKE '%PropertyPlant%' 
               OR source_tag ILIKE '%CapitalExp%')
        """
        count = conn.execute(q_count).fetchone()[0]
        print(f"Found {count} existing 'Other' mappings that should be re-evaluated for growth.")

        if count > 0:
            # 2. Delete them
            q_del = """
            DELETE FROM mapping_audit 
            WHERE target_label = 'Other' 
              AND (source_tag ILIKE '%Research%' 
                   OR source_tag ILIKE '%Development%' 
                   OR source_tag ILIKE '%PropertyPlant%' 
                   OR source_tag ILIKE '%CapitalExp%')
            """
            conn.execute(q_del)
            print("Successfully cleared mappings for re-evaluation.")
        else:
            print("No mappings found requiring upgrade.")


if __name__ == "__main__":
    upgrade_mappings()
