import zstandard as zstd
from src.shared.infra.db import db_manager

def validate_data():
    print("--- EDINET Data Quality Audit ---")
    try:
        with db_manager.connect_master(read_only=True) as conn:
            # 1. Check Registry (Filings)
            total_filings = conn.execute("SELECT count(*) FROM registry_db.filings").fetchone()[0]
            recent_filings = conn.execute("SELECT doc_id, filer_name, doc_description, submit_datetime FROM registry_db.filings ORDER BY submit_datetime DESC LIMIT 5").fetchall()
            
            print(f"\n[Registry] Total Filings: {total_filings}")
            print("Recent Entries:")
            for row in recent_filings:
                print(f"  - {row[3]} | {row[1]} | {row[2][:30]}... ({row[0]})")

            # 2. Check Facts
            total_facts = conn.execute("SELECT count(*) FROM facts_db.company_facts").fetchone()[0]
            sample_facts = conn.execute("SELECT item_name, item_value, unit, fiscal_year FROM facts_db.company_facts LIMIT 5").fetchall()
            
            print(f"\n[Facts] Total Facts: {total_facts}")
            print("Sample Data:")
            for row in sample_facts:
                print(f"  - {row[0]}: {row[1]} {row[2]} (FY{row[3]})")

            # 3. Check Narratives & Compression
            total_narratives = conn.execute("SELECT count(*) FROM narr_db.narratives").fetchone()[0]
            sample_narrative = conn.execute("SELECT doc_id, section_name, content_md FROM narr_db.narratives LIMIT 1").fetchone()
            
            print(f"\n[Narratives] Total Blocks: {total_narratives}")
            if sample_narrative:
                doc_id, section, content_blob = sample_narrative
                compressed_size = len(content_blob)
                try:
                    dctx = zstd.ZstdDecompressor()
                    decompressed = dctx.decompress(content_blob).decode('utf-8')
                    print(f"  - Sample Block (doc_id={doc_id}, section={section})")
                    print(f"  - Compression Status: OK (Compressed: {compressed_size} bytes -> Decompressed: {len(decompressed)} chars)")
                    print(f"  - Content Preview: {decompressed[:100]}...")
                except Exception as e:
                    print(f"  - Compression Error: {e}")
            else:
                print("  - No narratives found yet.")

    except Exception as e:
        print(f"\nCRITICAL: Validation failed - {e}")

if __name__ == "__main__":
    validate_data()
