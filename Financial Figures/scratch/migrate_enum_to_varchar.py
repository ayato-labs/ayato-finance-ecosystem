import duckdb


def migrate():
    db_path = "data/markets/us.duckdb"
    print(f"Opening {db_path}...")
    conn = duckdb.connect(db_path)

    try:
        # 1. Identify and Drop Indexes
        print("Dropping indexes...")
        conn.execute("DROP INDEX IF EXISTS idx_us_facts_lookup")

        # 2. Alter columns to VARCHAR
        columns = ["taxonomy", "form", "fiscal_period"]
        for col in columns:
            print(f"Altering {col} to VARCHAR...")
            try:
                conn.execute(f"ALTER TABLE company_facts ALTER {col} SET DATA TYPE VARCHAR")
            except Exception as e:
                print(f"  Error on {col}: {e}")

        # 3. Re-create indexes
        print("Re-creating index...")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_us_facts_lookup ON company_facts (cik, tag, end_date)"
        )

        print("Migration COMPLETED.")

        # 4. Verify
        print("\nVerifying schema:")
        res = conn.execute("DESCRIBE company_facts").fetchall()
        for r in res:
            print(f"  {r[0]}: {r[1]}")

    except Exception as e:
        print(f"MIGRATION FAILED: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
