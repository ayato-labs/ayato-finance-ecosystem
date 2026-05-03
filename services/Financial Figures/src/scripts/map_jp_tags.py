import time

from src.core.db import db_manager


def map_jp_tags():
    load_dotenv()

    # 1. Start Mapping Session
    session_id = audit_manager.start_session(market="MAPPER_JP")
    print(f"Mapping Session Started: {session_id}")

    mapper = AIMapper()

    # 2. Extract Top Unique Tags from JP DB
    print(f"Extracting top 30 most frequent JP tags from {settings.DB_PATH_JP}...")
    with db_manager.connect(settings.DB_PATH_JP, read_only=True) as conn:
        # get_fin_summary returns cols as tags. We pick the most frequent ones.
        tags = conn.execute("""
            SELECT taxonomy, tag, count(*) as freq
            FROM company_facts
            GROUP BY taxonomy, tag
            ORDER BY count(*) DESC
            LIMIT 30
        """).fetchall()

    print(f"Found {len(tags)} unique tags in JP database.")

    # 3. Check already mapped tags in Audit DB
    with db_manager.connect(settings.DB_PATH_TRACEABILITY, read_only=True) as conn:
        mapped_tags = set(
            r[0] for r in conn.execute("SELECT source_tag FROM mapping_audit").fetchall()
        )

    # 4. Process unknown tags
    mapped_count = 0
    errors_count = 0
    for taxonomy, tag, _freq in tags:
        source_key = f"JP:{tag}"
        if source_key in mapped_tags:
            continue

        print(f"Mapping {tag}...")
        try:
            mapper.map_tag(
                market="JP",
                tag=tag,
                description=f"Japan financial item from {taxonomy} (J-Quants V2 Summary)",
                session_id=session_id,
            )
            mapped_count += 1
            time.sleep(1)
        except Exception as e:
            print(f"FAILED to map {tag}: {e}")
            errors_count += 1

    # 5. End Session
    audit_manager.end_session(session_id, "SUCCESS", mapped_count, errors_count)
    print(f"\nJP Mapping Complete. New mappings: {mapped_count}, Errors: {errors_count}")


if __name__ == "__main__":
    map_jp_tags()
