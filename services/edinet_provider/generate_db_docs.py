import datetime
from src.core.schema import TABLE_DEFINITIONS

def generate_docs():
    """Generates DATABASE.md from Schema-as-Code definitions."""
    doc = []
    doc.append("# EDINET Provider Database Documentation")
    doc.append(f"*Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    
    doc.append("\n## Architecture: The Quad-Split (Master Governance)")
    doc.append("The system uses a Master database to orchestrate specialized storage shards via `ATTACH DATABASE`.")

    # Add Mermaid Diagram
    doc.append("\n### Database Relationship Diagram")
    doc.append("```mermaid")
    doc.append("erDiagram")
    doc.append("    MASTER ||--o{ REGISTRY : orchestrates")
    doc.append("    MASTER ||--o{ FACTS : orchestrates")
    doc.append("    MASTER ||--o{ NARRATIVE : orchestrates")
    doc.append("    REGISTRY_filings ||--o{ FACTS_company_facts : \"doc_id (PK)\"")
    doc.append("    REGISTRY_filings ||--o{ NARRATIVE_narratives : \"doc_id (PK)\"")
    doc.append("```")

    doc.append("\n## Database Shards")
    for db_alias, db_config in TABLE_DEFINITIONS.items():
        doc.append(f"\n### Database: `{db_alias}`")
        doc.append(f"**Description**: {db_config['description']}")
        
        for t_name, t_config in db_config["tables"].items():
            doc.append(f"\n#### Table: `{t_name}`")
            doc.append(f"{t_config['description']}")
            doc.append("\n```sql")
            doc.append(t_config["ddl"].strip())
            doc.append("```")

    with open("DATABASE.md", "w", encoding="utf-8") as f:
        f.write("\n".join(doc))
    print("✅ DATABASE.md generated successfully.")

if __name__ == "__main__":
    generate_docs()
