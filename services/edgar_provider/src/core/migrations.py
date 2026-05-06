from loguru import logger

from src.core.db import db_manager
from src.core.generated_schema import INDEX_SCHEMAS, TABLE_SCHEMAS


def apply_initial_schema(conn, role: str = None):
    """Applies the base schema generated from contracts."""
    # Heuristic to detect role if not provided
    if not role:
        db_info = conn.execute("PRAGMA database_list").fetchall()
        # db_info is list of (seq, name, file)
        db_file = ""
        for row in db_info:
            if row[1] == "main":
                db_file = row[2].lower()
                break

        if "facts" in db_file:
            role = "facts"
        elif "narratives" in db_file:
            role = "narratives"

    is_facts_db = role == "facts"
    is_narratives_db = role == "narratives"

    for table_name, versions in TABLE_SCHEMAS.items():
        # Routing logic:
        if is_facts_db and table_name == "narratives":
            continue
        if is_narratives_db and table_name in ["company_facts", "filings", "tickers"]:
            continue

        exists = (
            conn.execute(
                f"SELECT count(*) FROM information_schema.tables WHERE table_name = '{table_name}'"
            ).fetchone()[0]
            > 0
        )
        if not exists:
            sql = versions if isinstance(versions, str) else versions.get("v1")
            conn.execute(sql)

    # Apply relevant indexes
    for index_sql in INDEX_SCHEMAS:
        if is_facts_db and "narratives" in index_sql.lower():
            continue
        if is_narratives_db and "company_facts" in index_sql.lower():
            continue
        conn.execute(index_sql)


def optimize_data_types_v1_0_1(conn, role: str = None):
    """Downgrade TIMESTAMP to DATE and INTEGER to SMALLINT for storage efficiency."""
    if not role:
        db_info = conn.execute("PRAGMA database_list").fetchall()
        db_file = ""
        for row in db_info:
            if row[1] == "main":
                db_file = row[2].lower()
                break
        if "facts" in db_file:
            role = "facts"
        elif "narratives" in db_file:
            role = "narratives"

    is_facts_db = role == "facts"
    is_narratives_db = role == "narratives"

    # Drop indexes to avoid Dependency Error in DuckDB
    if is_facts_db:
        conn.execute("DROP INDEX IF EXISTS idx_us_facts_lookup;")
    if is_narratives_db:
        conn.execute("DROP INDEX IF EXISTS idx_us_narratives_lookup;")

    tables = [
        r[0] for r in conn.execute("SELECT table_name FROM information_schema.tables").fetchall()
    ]

    if is_facts_db and "company_facts" in tables:
        conn.execute("ALTER TABLE company_facts ALTER filed_date SET DATA TYPE DATE;")
        conn.execute("ALTER TABLE company_facts ALTER fiscal_year SET DATA TYPE SMALLINT;")
    if is_narratives_db and "narratives" in tables:
        conn.execute("ALTER TABLE narratives ALTER filed_date SET DATA TYPE DATE;")

    # Recreate relevant indexes
    for index_sql in INDEX_SCHEMAS:
        if is_facts_db and "company_facts" in index_sql.lower():
            conn.execute(index_sql)
        if is_narratives_db and "narratives" in index_sql.lower():
            conn.execute(index_sql)


# List of all migrations in chronological order.
MIGRATIONS = [
    {
        "version": "v1.0.0",
        "description": "Initial schema based on Data Contracts",
        "apply": apply_initial_schema,
    },
    {
        "version": "v1.0.1",
        "description": (
            "Optimize data types for storage efficiency "
            "(filed_date to DATE, fiscal_year to SMALLINT)"
        ),
        "apply": optimize_data_types_v1_0_1,
    },
]


class MigrationManager:
    @staticmethod
    def _ensure_migrations_table(conn):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR PRIMARY KEY,
                description VARCHAR,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    @staticmethod
    def _get_applied_versions(conn):
        try:
            results = conn.execute("SELECT version FROM schema_migrations").fetchall()
            return {row[0] for row in results}
        except Exception:
            return set()

    @staticmethod
    def apply_migrations(db_path):
        logger.info(f"Checking migrations for {db_path}...")
        with db_manager.connect(db_path) as conn:
            # 1. Ensure the tracking table exists
            MigrationManager._ensure_migrations_table(conn)

            # 2. Get already applied versions
            applied = MigrationManager._get_applied_versions(conn)

            # 3. Apply missing migrations in order
            for migration in MIGRATIONS:
                version = migration["version"]
                if version not in applied:
                    logger.info(f"Applying migration {version}: {migration['description']}")
                    try:
                        # Execute the migration logic
                        migration["apply"](conn)

                        # Record the migration
                        conn.execute(
                            "INSERT INTO schema_migrations (version, description) VALUES (?, ?)",
                            [version, migration["description"]],
                        )
                        logger.info(f"Successfully applied {version}.")
                    except Exception as e:
                        logger.error(f"Migration {version} failed: {e}")
                        raise e

        logger.info("Database is up to date.")
