import datetime as dt
from typing import ClassVar
from pydantic import BaseModel, Field


class BaseDbSchema(BaseModel):
    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class DocumentManifestSchema(BaseDbSchema):
    doc_id: str = Field(..., description="Unique document ID index (Primary Key)")
    status: str | None = Field(None, description="Current ingestion processing status")
    updated_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="DB record update timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"},
    )

    class SQLConfig:
        table_name: ClassVar[str] = "document_manifest"
        primary_key: ClassVar[list[str]] = ["doc_id"]


class FilingSchema(BaseDbSchema):
    doc_id: str = Field(..., description="Unique document ID (Primary Key)")
    edinet_code: str | None = Field(None, description="Submitter EDINET identification code")
    sec_code: str | None = Field(None, description="Submitter security ticker code")
    filer_name: str | None = Field(None, description="Corporate company name of the filer")
    doc_description: str | None = Field(None, description="Document type description text")
    submit_datetime: dt.datetime | None = Field(
        None, description="EDINET official submission timestamp"
    )
    form_code: str | None = Field(None, description="Type form category code")
    doc_type_code: str | None = Field(
        None, description="Specific document type category classification number"
    )
    session_id: str | None = Field(None, description="Sync execution logging session ID")
    ingested_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="DB record insertion timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"},
    )

    class SQLConfig:
        table_name: ClassVar[str] = "filings"
        primary_key: ClassVar[list[str]] = ["doc_id"]


class CompanyFactSchema(BaseDbSchema):
    doc_id: str = Field(..., description="Associated document ID key")
    item_name: str = Field(..., description="XBRL taxonomy item account name")
    item_value: float | None = Field(None, description="Numerical value of the fact")
    unit: str | None = Field(None, description="Units classification (e.g. JPY, Shares)")
    context_id: str = Field(..., description="Filing statement context description ID")
    fiscal_year: int | None = Field(None, description="Target accounting fiscal year")
    fiscal_period: str | None = Field(
        None, description="Target fiscal period (e.g. FY, Q1, Q2, Q3)"
    )
    session_id: str | None = Field(None, description="Sync execution logging session ID")
    ingested_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="DB record insertion timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"},
    )

    class SQLConfig:
        table_name: ClassVar[str] = "company_facts"
        primary_key: ClassVar[list[str]] = ["doc_id", "item_name", "context_id"]


class NarrativeSchema(BaseDbSchema):
    doc_id: str = Field(..., description="Associated document ID key")
    section_name: str = Field(..., description="Qualitative paragraph section category name")
    content_md: str | None = Field(
        None, description="Parsed text body content formatted in Markdown"
    )
    session_id: str | None = Field(None, description="Sync execution logging session ID")
    ingested_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="DB record insertion timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"},
    )

    class SQLConfig:
        table_name: ClassVar[str] = "narratives"
        primary_key: ClassVar[list[str]] = ["doc_id", "section_name"]


class FinancialStatementSchema(BaseDbSchema):
    doc_id: str = Field(..., description="Unique document ID (Primary Key)")
    edinet_code: str | None = Field(None, description="Submitter EDINET identification code")
    sec_code: str | None = Field(None, description="Submitter security ticker code")
    fiscal_year: int | None = Field(None, description="Target accounting fiscal year")
    fiscal_period: str | None = Field(
        None, description="Target fiscal period (e.g. FY, Q1, Q2, Q3)"
    )
    submit_datetime: dt.datetime | None = Field(
        None, description="EDINET official submission timestamp"
    )
    current_assets: int | None = Field(None, description="Balance Sheet: Current assets")
    cash_and_deposits: int | None = Field(
        None, description="Balance Sheet: Cash and cash equivalents"
    )
    total_assets: int | None = Field(None, description="Balance Sheet: Total assets")
    current_liabilities: int | None = Field(None, description="Balance Sheet: Current liabilities")
    total_liabilities: int | None = Field(None, description="Balance Sheet: Total liabilities")
    net_assets: int | None = Field(None, description="Balance Sheet: Total net assets")
    net_sales: int | None = Field(None, description="Income Statement: Net sales / revenue")
    operating_income: int | None = Field(None, description="Income Statement: Operating income")
    net_income: int | None = Field(None, description="Income Statement: Net income")
    is_equation_valid: bool | None = Field(
        None, description="Status validity validation of balance identity equation"
    )
    is_consolidated: bool | None = Field(
        None, description="Boolean flag if financials are consolidated statements"
    )
    interest_expense: int | None = Field(
        None, description="Income Statement: Interest expense value"
    )
    operating_cash_flow: int | None = Field(
        None, description="Cash Flow Statement: Net cash from operating activities"
    )
    industry_code: str | None = Field(None, description="Industrial classification mapping code")

    class SQLConfig:
        table_name: ClassVar[str] = "financial_statements"
        primary_key: ClassVar[list[str]] = ["doc_id"]


class IngestionLogSchema(BaseDbSchema):
    doc_id: str = Field(..., description="Unique document ID key (Primary Key)")
    status: str | None = Field(None, description="Ingestion processing outcome status")
    last_attempt: dt.datetime | None = Field(
        None, description="Timestamp of the last processing attempt"
    )
    retry_count: int = Field(
        0,
        description="Counter of historical retry attempts",
        json_schema_extra={"sql_default": "0"},
    )
    error_message: str | None = Field(None, description="Detailed trace logs if attempt failed")

    class SQLConfig:
        table_name: ClassVar[str] = "ingestion_log"
        primary_key: ClassVar[list[str]] = ["doc_id"]


class IngestionProgressSchema(BaseDbSchema):
    target_date: dt.date = Field(
        ..., description="Date calendar point of EDINET listings check (Primary Key)"
    )
    status: str | None = Field(None, description="Processing status of the calendar date sync")
    doc_count: int | None = Field(None, description="Total documents processed on this date")
    updated_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="DB record update timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"},
    )

    class SQLConfig:
        table_name: ClassVar[str] = "ingestion_progress"
        primary_key: ClassVar[list[str]] = ["target_date"]


import types
from typing import Any, get_args, get_origin, Union
from pathlib import Path

TYPE_MAPPING = {
    str: "VARCHAR",
    int: "BIGINT",
    float: "DOUBLE",
    dt.datetime: "TIMESTAMP",
    dt.date: "DATE",
    bool: "BOOLEAN",
}


def resolve_sql_type(
    field_type: Any, field_name: str, type_overrides: dict[str, str] = None
) -> str:
    if type_overrides and field_name in type_overrides:
        return type_overrides[field_name]

    # Handle Optional types / Unions (including Python 3.10+ UnionType)
    origin = get_origin(field_type)
    if (
        origin is Union
        or origin == type(Union)
        or (hasattr(types, "UnionType") and origin is types.UnionType)
    ):
        args = get_args(field_type)
        # Filter out NoneType (type(None))
        non_none_args = [arg for arg in args if arg is not type(None)]
        if non_none_args:
            return resolve_sql_type(non_none_args[0], field_name, type_overrides)

    if field_type in TYPE_MAPPING:
        return TYPE_MAPPING[field_type]

    # Fallback to JSON or VARCHAR
    if origin in (dict, list) or field_type is Any:
        return "JSON"

    return "VARCHAR"


def generate_schema_files(output_dir: Path):
    schemas = [
        DocumentManifestSchema,
        FilingSchema,
        CompanyFactSchema,
        NarrativeSchema,
        FinancialStatementSchema,
        IngestionLogSchema,
        IngestionProgressSchema,
    ]

    sql_statements = []
    markdown_sections = []
    markdown_sections.append(
        "# database_design.md\n\nThis document describes the schema of the EDINET Provider DuckDB database files."
    )

    for schema_cls in schemas:
        config = getattr(schema_cls, "SQLConfig", None)
        table_names = []
        if config:
            if hasattr(config, "table_names"):
                table_names = config.table_names
            elif hasattr(config, "table_name"):
                table_names = [config.table_name]

        if not table_names:
            table_names = [schema_cls.__name__.lower().replace("schema", "")]

        primary_keys = getattr(config, "primary_key", [])
        unique_constraints = getattr(config, "unique_constraints", [])
        type_overrides = getattr(config, "type_overrides", {})

        fields_ddl = []
        md_fields_table = [
            "| Column | Type | Default | Description |",
            "| :--- | :--- | :--- | :--- |",
        ]

        for name, field in schema_cls.model_fields.items():
            sql_type = resolve_sql_type(field.annotation, name, type_overrides)
            constraints = []
            if name in primary_keys and len(primary_keys) == 1:
                constraints.append("PRIMARY KEY")

            default_val = "NULL"
            sql_extra = field.json_schema_extra or {}
            if "sql_default" in sql_extra:
                default_val = sql_extra["sql_default"]
                constraints.append(f"DEFAULT {default_val}")
            elif field.default is not None and field.default != ...:
                if isinstance(field.default, (int, float, bool)):
                    default_val = str(field.default).upper()
                    constraints.append(f"DEFAULT {default_val}")
                elif isinstance(field.default, str):
                    default_val = f"'{field.default}'"
                    constraints.append(f"DEFAULT {default_val}")

            field_ddl = f"{name} {sql_type}"
            if constraints:
                field_ddl += " " + " ".join(constraints)
            fields_ddl.append(field_ddl)

            desc = field.description or "No description provided."
            md_fields_table.append(f"| `{name}` | **{sql_type}** | `{default_val}` | {desc} |")

        for uq in unique_constraints:
            fields_ddl.append(f"UNIQUE ({', '.join(uq)})")
        if len(primary_keys) > 1:
            fields_ddl.append(f"PRIMARY KEY ({', '.join(primary_keys)})")

        for table_name in table_names:
            ddl = f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
            ddl += ",\n".join(f"    {line}" for line in fields_ddl)
            ddl += "\n);"
            sql_statements.append(ddl)

            md_sec = f"\n## Table: `{table_name}`\n\n"
            md_sec += f"**Description**: {schema_cls.__doc__ or 'No description provided.'}\n\n"
            if primary_keys:
                md_sec += f"- **Primary Key**: `{', '.join(primary_keys)}`\n"
            if unique_constraints:
                md_sec += f"- **Unique Constraints**:\n"
                for uq in unique_constraints:
                    md_sec += f"  - `({', '.join(uq)})`\n"
            md_sec += "\n" + "\n".join(md_fields_table) + "\n"
            markdown_sections.append(md_sec)

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "schema.sql").write_text("\n\n".join(sql_statements) + "\n", encoding="utf-8")
        (output_dir / "database_design.md").write_text(
            "\n".join(markdown_sections) + "\n", encoding="utf-8"
        )
    except Exception as e:
        print(f"Warning: Failed to auto-update EDINET schema files: {e}")
