import time
from pathlib import Path

import duckdb

US_DB = Path("data/markets/us.duckdb")


def resume_migration():
    if not US_DB.exists():
        print(f"Error: {US_DB} not found.")
        return

    print("Resuming US migration from company_facts_old...")
    start_time = time.perf_counter()

    with duckdb.connect(str(US_DB)) as conn:
        # Check initial state
        tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
        if "company_facts_old" not in tables:
            print("Error: company_facts_old table not found! No data to migrate from.")
            return

        old_row_count = conn.execute("SELECT count(*) FROM company_facts_old").fetchone()[0]
        if old_row_count == 0:
            print("Error: company_facts_old is EMPTY. Something is wrong.")
            return

        print(f"Source Row Count (company_facts_old): {old_row_count}")

        # 1. Discover ENUM values from the SOURCE (old table)
        print("Discovering unique values for ENUMs from company_facts_old...")
        taxonomies = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT taxonomy FROM company_facts_old WHERE taxonomy IS NOT NULL"
            ).fetchall()
        ]
        periods = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT fiscal_period FROM company_facts_old WHERE fiscal_period IS NOT NULL"
            ).fetchall()
        ]
        forms = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT form FROM company_facts_old WHERE form IS NOT NULL"
            ).fetchall()
        ]

        def format_enum_list(vals):
            escaped_vals = [str(v).replace("'", "''") for v in vals]
            return "(" + ", ".join(f"'{v}'" for v in escaped_vals) + ")"

        print("Re-creating optimized types...")
        conn.execute("DROP TYPE IF EXISTS taxonomy_enum CASCADE")
        conn.execute("DROP TYPE IF EXISTS period_enum CASCADE")
        conn.execute("DROP TYPE IF EXISTS form_enum CASCADE")
        conn.execute(f"CREATE TYPE taxonomy_enum AS ENUM {format_enum_list(taxonomies)}")
        conn.execute(f"CREATE TYPE period_enum AS ENUM {format_enum_list(periods)}")
        conn.execute(f"CREATE TYPE form_enum AS ENUM {format_enum_list(forms)}")

        # 2. Re-create optimized company_facts table (ensure it's clean)
        print("Dropping existing empty company_facts and re-creating...")
        conn.execute("DROP INDEX IF EXISTS idx_us_facts_lookup")
        conn.execute("DROP TABLE IF EXISTS company_facts")
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

        # 3. Migrate and Sort (Final attempt)
        print("Migrating data with physical sorting (this will take time)...")
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

        if new_row_count != old_row_count:
            raise Exception(
                f"DATA INTEGRITY FAILURE: Row count mismatch ({new_row_count} vs {old_row_count})"
            )

        # 4. Cleanup
        print("Dropping old table (company_facts_old)...")
        conn.execute("DROP TABLE company_facts_old")

        # 5. Recreate Index
        print("Recreating lookup index...")
        conn.execute("CREATE INDEX idx_us_facts_lookup ON company_facts (cik, tag, end_date DESC)")

        # 6. Checkpoint
        print("Checkpointing to finalize storage optimization...")
        conn.execute("CHECKPOINT")

    duration = time.perf_counter() - start_time
    print(f"US Optimization finished in {duration:.2f} seconds.")


if __name__ == "__main__":
    resume_migration()
