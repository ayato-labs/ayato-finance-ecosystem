import sys
from pathlib import Path

# Add project root to sys.path to import src
sys.path.append(str(Path(__file__).parent.parent))

from src.core.schema import TABLE_SCHEMAS, CATALOG_SCHEMA


def generate_markdown():
    """Generates a Markdown document summarizing the database schema."""
    lines = [
        "# J-Quants Provider Database Schema Definition",
        "",
        "> [!IMPORTANT]",
        "> This document is automatically generated from `src/core/schema.py`. Do not edit manually.",
        "",
        "## Overview",
        "This project uses DuckDB for historical data storage. Sharding is supported, and all shards are tracked via a central master catalog.",
        "",
        "## Table Definitions",
        "",
    ]

    # Combined all schemas for documentation
    all_schemas = {**TABLE_SCHEMAS, **CATALOG_SCHEMA}

    for table_name, info in all_schemas.items():
        lines.append(f"### `{table_name}`")
        lines.append(f"- **Version**: {info['version']}")
        lines.append(f"- **Description**: {info['description']}")
        lines.append("")
        lines.append("#### SQL Schema")
        lines.append("```sql")
        # Strip leading whitespace from each line for cleaner SQL blocks
        sql_clean = "\n".join([line.strip() for line in info["sql"].strip().split("\n")])
        lines.append(sql_clean)
        lines.append("```")
        lines.append("")

    lines.append("## Indices")
    lines.append("The following indices are applied to optimize query performance:")
    lines.append("```sql")
    from src.core.schema import INDEX_SCHEMAS

    for idx in INDEX_SCHEMAS:
        lines.append(idx)
    lines.append("```")

    return "\n".join(lines)


if __name__ == "__main__":
    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)

    md_content = generate_markdown()

    output_path = docs_dir / "DATABASE.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"✅ Documentation successfully generated at: {output_path}")
