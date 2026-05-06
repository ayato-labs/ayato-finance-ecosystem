import shutil
import time
from pathlib import Path

import duckdb

US_DB = Path("data/markets/us.duckdb")
BACKUP_DB = Path("data/markets/us.duckdb.pre_migration")


def migrate_us():
    if not US_DB.exists():
        print(f"Error: {US_DB} not found.")
        return

    print(f"Creating mandatory safety backup: {BACKUP_DB}...")
    shutil.copy2(US_DB, BACKUP_DB)

    print(f"Starting US migration (v2) for {US_DB}...")
    start_time = time.perf_counter()

    with duckdb.connect(str(US_DB)) as conn:
        # Check initial state
        tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
        if "company_facts" not in tables:
            print("Error: company_facts table not found in current DB!")
            return

        row_count = conn.execute("SELECT count(*) FROM company_facts").fetchone()[0]
        if row_count == 0:
            print("Error: company_facts is EMPTY. Migration aborted to prevent data loss.")
            return

        print(f"Current Row Count: {row_count}")

        # 1. Discover ENUM values from the SOURCE
        print("Discovering unique values for ENUMs...")
        taxonomies = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT taxonomy FROM company_facts WHERE taxonomy IS NOT NULL"
            ).fetchall()
        ]
        periods = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT fiscal_period FROM company_facts WHERE fiscal_period IS NOT NULL"
            ).fetchall()
        ]
        forms = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT form FROM company_facts WHERE form IS NOT NULL"
            ).fetchall()
        ]

        def format_enum_list(vals):
            escaped_vals = [str(v).replace("'", "''") for v in vals]
            return "(" + ", ".join(f"'{v}'" for v in escaped_vals) + ")"

        print("Creating ENUM types...")
        conn.execute("DROP TYPE IF EXISTS taxonomy_enum CASCADE")
        conn.execute("DROP TYPE IF EXISTS period_enum CASCADE")
        conn.execute("DROP TYPE IF EXISTS form_enum CASCADE")
        conn.execute(f"CREATE TYPE taxonomy_enum AS ENUM {format_enum_list(taxonomies)}")
        conn.execute(f"CREATE TYPE period_enum AS ENUM {format_enum_list(periods)}")
        conn.execute(f"CREATE TYPE form_enum AS ENUM {format_enum_list(forms)}")

        # 2. Rename existing table
        print("Renaming company_facts to company_facts_old...")
        conn.execute("DROP INDEX IF EXISTS idx_us_facts_lookup")
        conn.execute("ALTER TABLE company_facts RENAME TO company_facts_old")

        # 3. Create optimized table
        print("Creating optimized company_facts table...")
        conn.execute("""
            CREATE TABLE company_facts (
                fact_id VARCHAR PRIMARY KEY,
                cik VARCHAR,
                taxonomy taxonomy_enum,
                tag VARCHAR,
                label VARCHAR,
                unit VARCHAR,
                value DOUBLE,
                end_date DATE,
                fiscal_year INTEGER,
                fiscal_period period_enum,
                form form_enum,
                filed_date DATE,
                accession_number VARCHAR,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                session_id VARCHAR
            )
        """)

        # 4. Migrate and Sort
        print("Migrating data with physical sorting...")
        conn.execute("""
            INSERT INTO company_facts (
                fact_id, cik, taxonomy, tag, label, unit, value, end_date,
                fiscal_year, fiscal_period, form, filed_date, accession_number, session_id
            )
            SELECT
                md5(concat_ws('|', cik, taxonomy, tag, end_date, accession_number)) as fact_id,
                cik,
                taxonomy::taxonomy_enum,
                tag, label, unit, value, end_date,
                fiscal_year,
                fiscal_period::period_enum,
                form::form_enum,
                filed_date, accession_number, session_id
            FROM company_facts_old
            ORDER BY cik, tag, end_date DESC
        """)

        new_row_count = conn.execute("SELECT count(*) FROM company_facts").fetchone()[0]
        print(f"Migration completed. {new_row_count} records processed.")

        if new_row_count != row_count:
            raise Exception(
                f"DATA INTEGRITY FAILURE: Row count mismatch ({new_row_count} vs {row_count})"
            )

        # 5. Cleanup
        print("Dropping old table...")
        conn.execute("DROP TABLE company_facts_old")

        # 6. Recreate Index
        print("Recreating lookup index...")
        conn.execute("CREATE INDEX idx_us_facts_lookup ON company_facts (cik, tag, end_date DESC)")

        # 7. Checkpoint
        print("Checkpointing...")
        conn.execute("CHECKPOINT")

    duration = time.perf_counter() - start_time
    print(f"Done in {duration:.2f}s.")


if __name__ == "__main__":
    try:
        migrate_us()
    except Exception as e:
        print(f"Migration Failed: {e}")
        # Restoration logic if failed after renaming
        # Note: In a real script, we would automatically rename back us.duckdb.pre_migration
