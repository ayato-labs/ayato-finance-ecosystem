import datetime as dt
from typing import ClassVar

from pydantic import BaseModel, Field


class BaseDbSchema(BaseModel):
    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class CategorySchema(BaseDbSchema):
    category_id: int = Field(..., description="ID of the FRED category (Primary Key)")
    name: str | None = Field(None, description="Name of the category")
    last_audited: dt.datetime | None = Field(
        None, description="Timestamp when the category was last audited"
    )

    class SQLConfig:
        table_name: ClassVar[str] = "categories"
        primary_key: ClassVar[list[str]] = ["category_id"]


class CategorySeriesSchema(BaseDbSchema):
    category_id: int = Field(..., description="Category ID mapping")
    series_id: str = Field(..., description="Series ID mapping")

    class SQLConfig:
        table_name: ClassVar[str] = "category_series"
        primary_key: ClassVar[list[str]] = ["category_id", "series_id"]


class ObservationSchema(BaseDbSchema):
    series_id: str = Field(..., description="FRED series symbol key")
    date: dt.date = Field(..., description="Date of the macro economic observation")
    value: float | None = Field(None, description="Numerical value of the observation on this date")

    class SQLConfig:
        table_name: ClassVar[str] = "observations"
        primary_key: ClassVar[list[str]] = ["series_id", "date"]


class SeriesMetadataSchema(BaseDbSchema):
    series_id: str = Field(..., description="FRED series symbol key (Primary Key)")
    title: str | None = Field(None, description="Title name of the macroeconomic series")
    units: str | None = Field(None, description="Reporting measurement units")
    frequency: str | None = Field(
        None, description="Measurement update frequency (e.g. Daily, Monthly)"
    )
    seasonal_adjustment: str | None = Field(None, description="Seasonal adjustment status text")
    last_updated: dt.datetime | None = Field(
        None, description="Timestamp when series was last updated by FRED"
    )
    notes: str | None = Field(None, description="Detailed explanatory notes regarding the series")
    observation_start: dt.date | None = Field(
        None, description="Start date of historical observations"
    )
    observation_end: dt.date | None = Field(None, description="End date of historical observations")

    class SQLConfig:
        table_name: ClassVar[str] = "series_metadata"
        primary_key: ClassVar[list[str]] = ["series_id"]


import types
from pathlib import Path
from typing import Any, Union, get_args, get_origin

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
        CategorySchema,
        CategorySeriesSchema,
        ObservationSchema,
        SeriesMetadataSchema,
    ]

    sql_statements = []
    markdown_sections = []
    markdown_sections.append(
        "# database_design.md\n\nThis document describes the schema of the FRED Provider DuckDB database."
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
                md_sec += "- **Unique Constraints**:\n"
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
        print(f"Warning: Failed to auto-update FRED schema files: {e}")
