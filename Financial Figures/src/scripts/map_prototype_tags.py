import time

import duckdb
from dotenv import load_dotenv

from src.core.audit_manager import audit_manager
from src.core.config import settings
from src.mappers.ai_mapper import AIMapper


def map_all_tags():
    load_dotenv()

    # 1. Start Mapping Session
    session_id = audit_manager.start_session(market="MAPPER_US")
    print(f"Mapping Session Started: {session_id}")

    mapper = AIMapper()

    # 2. Extract Top Unique Tags from US DB (Optimization for Prototype)
    print(f"Extracting top 50 most frequent tags from {settings.DB_PATH_US}...")
    with duckdb.connect(str(settings.DB_PATH_US)) as conn:
        # Get taxonomy and tag combinations, ordered by frequency
        tags = conn.execute("""
            SELECT taxonomy, tag, count(*) as freq
            FROM company_facts
            GROUP BY taxonomy, tag
            ORDER BY count(*) DESC
            LIMIT 50
        """).fetchall()

    print(f"Found {len(tags)} unique tags in database.")

    # 3. Check already mapped tags in Audit DB
    audit_db_path = settings.DATA_DIR / "audit" / "traceability.duckdb"
    with duckdb.connect(str(audit_db_path)) as conn:
        mapped_tags = set(
            r[0] for r in conn.execute("SELECT source_tag FROM mapping_audit").fetchall()
        )

    print(f"{len(mapped_tags)} tags are already mapped.")

    # 4. Process unknown tags
    mapped_count = 0
    errors_count = 0
    for taxonomy, tag, _freq in tags:
        source_key = f"US:{tag}"  # We use US as market prefix in mapper
        if source_key in mapped_tags:
            continue

        print(f"Mapping {tag}...")
        try:
            # We don't have descriptions in the company_facts table yet.
            # For the prototype, we rely on the tag name itself for semantic mapping.
            mapper.map_tag(
                market="US",
                tag=tag,
                description=f"Financial item from taxonomy {taxonomy}",
                session_id=session_id,
            )
            mapped_count += 1
            # Rate limiting for AI
            time.sleep(1)
        except Exception as e:
            print(f"FAILED to map {tag}: {e}")
            errors_count += 1

    # 5. End Session
    audit_manager.end_session(session_id, "SUCCESS", mapped_count, errors_count)
    print(f"\nMapping Complete. New mappings: {mapped_count}, Errors: {errors_count}")


if __name__ == "__main__":
    map_all_tags()
