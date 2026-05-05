import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.schema import TABLE_SCHEMAS, CATALOG_SCHEMA

def generate_markdown():
    output = []
    output.append("# Database Schema Documentation")
    output.append("\n*This document is automatically generated from the Schema-as-Code definition in `src/core/schema.py`.*")
    
    output.append("\n## Table of Contents")
    for table_name in TABLE_SCHEMAS.keys():
        output.append(f"- [{table_name}](#{table_name.replace('_', '-')})")
    
    output.append("\n---")
    
    for table_name, schema in TABLE_SCHEMAS.items():
        output.append(f"\n## {table_name}")
        output.append(f"\n**Description:** {schema.get('description', 'N/A')}")
        output.append(f"\n**Shard:** `{schema.get('shard', 'master')}`")
        output.append(f"\n**Version:** {schema.get('version', 1)}")
        
        if "columns" in schema:
            output.append("\n### Columns")
            output.append("| Column | Description |")
            output.append("| --- | --- |")
            for col, desc in schema["columns"].items():
                output.append(f"| {col} | {desc} |")
        
        output.append("\n### SQL Definition")
        output.append("```sql")
        output.append(schema["sql"].strip())
        output.append("```")
        output.append("\n---")

    # Catalog
    output.append("\n## Catalog Manager (master.duckdb)")
    for table_name, schema in CATALOG_SCHEMA.items():
        output.append(f"\n### {table_name}")
        output.append(f"\n{schema.get('description', 'N/A')}")
        output.append("\n```sql")
        output.append(schema["sql"].strip())
        output.append("```")

    docs_dir = Path(__file__).parent.parent / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    with open(docs_dir / "DATABASE_SCHEMA.md", "w", encoding="utf-8") as f:
        f.write("\n".join(output))
    
    print(f"Documentation generated at {docs_dir / 'DATABASE_SCHEMA.md'}")

if __name__ == "__main__":
    generate_markdown()
