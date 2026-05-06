import datetime
import re
from src.core.schema import TABLE_DEFINITIONS

def parse_columns_from_ddl(ddl: str):
    """Simple parser to extract column names and types from DDL."""
    # Remove newlines and extra spaces
    clean_ddl = " ".join(ddl.split())
    # Find content between parentheses
    match = re.search(r"\((.*)\)", clean_ddl)
    if not match:
        return []
    
    content = match.group(1)
    # Split by comma, but ignore commas inside parentheses (like DECIMAL(10,2))
    # For now, a simple split is usually enough for this project's schema
    columns = []
    # Very basic parsing: split by comma, then take first two words
    parts = content.split(",")
    for part in parts:
        part = part.strip()
        if not part or part.upper().startswith("PRIMARY KEY"):
            continue
        sub_parts = part.split()
        if len(sub_parts) >= 2:
            name = sub_parts[0]
            col_type = sub_parts[1]
            constraints = " ".join(sub_parts[2:]) if len(sub_parts) > 2 else ""
            columns.append({"name": name, "type": col_type, "constraints": constraints})
    return columns

def generate_docs():
    """Generates DATABASE.md from Schema-as-Code definitions."""
    doc = []
    doc.append("# EDINET Provider Database Governance Documentation")
    doc.append(f"*Last Updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    
    doc.append("\n## 1. Governance Model: The Quad-Split")
    doc.append("The system adheres to a **Local-First Financial Data Infrastructure** pattern. "
               "It separates concerns across four physical storage shards to optimize for scalability, "
               "compression, and specialized access patterns.")

    # Add Mermaid Diagram
    doc.append("\n### Database Relationship Architecture")
    doc.append("```mermaid")
    doc.append("erDiagram")
    doc.append("    MASTER_DB ||--o{ REGISTRY_DB : \"manages via ATTACH\"")
    doc.append("    MASTER_DB ||--o{ FACTS_DB : \"manages via ATTACH\"")
    doc.append("    MASTER_DB ||--o{ NARR_DB : \"manages via ATTACH\"")
    doc.append("    REGISTRY_DB_filings ||--o{ FACTS_DB_company_facts : \"doc_id (FK)\"")
    doc.append("    REGISTRY_DB_filings ||--o{ NARR_DB_narratives : \"doc_id (FK)\"")
    doc.append("    MASTER_DB_ingestion_log ||--|| REGISTRY_DB_filings : \"tracks\"")
    doc.append("```")

    doc.append("\n## 2. Reliability Layer (Data Contracts)")
    doc.append("All ingestion is validated against Pydantic models defined in `src/core/contracts.py`. "
               "This ensures type safety and ticker normalization before data hits the storage layer.")

    doc.append("\n## 3. Data Dictionary")
    for db_alias, db_config in TABLE_DEFINITIONS.items():
        doc.append(f"\n### Shard: `{db_alias}`")
        doc.append(f"> {db_config['description']}")
        
        for t_name, t_config in db_config["tables"].items():
            doc.append(f"\n#### Table: `{t_name}`")
            doc.append(f"**Description**: {t_config['description']}")
            
            model = t_config.get("model")
            if model:
                doc.append(f"**Data Contract**: `{model.__name__}`")
            
            columns = parse_columns_from_ddl(t_config["ddl"])
            if columns:
                doc.append("\n| Column | Type | Constraints |")
                doc.append("| :--- | :--- | :--- |")
                for col in columns:
                    doc.append(f"| `{col['name']}` | `{col['type']}` | {col['constraints']} |")

            doc.append("\n<details><summary>View Raw DDL</summary>")
            doc.append("\n```sql")
            doc.append(t_config["ddl"].strip())
            doc.append("```")
            doc.append("</details>")

    doc.append("\n## 4. Lifecycle Management")
    doc.append("Database migrations are handled by the `MigrationManager` (Master-led). "
               "It synchronizes the SSoT schema and applies incremental SQL files from the `migrations/` directory.")

    with open("DATABASE.md", "w", encoding="utf-8") as f:
        f.write("\n".join(doc))
    print("✅ DATABASE.md generated successfully with advanced diagnostics.")

if __name__ == "__main__":
    generate_docs()
