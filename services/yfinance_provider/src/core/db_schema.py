import datetime as dt
from typing import Any, ClassVar
from pydantic import BaseModel, Field


class BaseDbSchema(BaseModel):
    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class SyncStatusSchema(BaseDbSchema):
    ticker: str = Field(..., description="Ticker symbol of the financial asset (Primary Key)")
    last_sync_at: dt.datetime = Field(..., description="Timestamp when the sync was performed")
    last_status: str = Field(..., description="Sync outcome status (e.g. SUCCESS, FAILED, PARTIAL)")
    error_message: str | None = Field(None, description="Detailed error message if sync failed")
    quality_score: float = Field(1.0, description="Calculated data quality score (0.0 to 1.0)")
    updated_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="Record update timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"},
    )

    class SQLConfig:
        table_name: ClassVar[str] = "sync_status"
        primary_key: ClassVar[list[str]] = ["ticker"]


class InfoSchema(BaseDbSchema):
    ticker: str = Field(..., description="Ticker symbol of the asset (Primary Key)")
    data: Any = Field(..., description="Raw stock profile info stored in JSON format")
    updated_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="Record update timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"},
    )

    class SQLConfig:
        table_name: ClassVar[str] = "info"
        primary_key: ClassVar[list[str]] = ["ticker"]
        type_overrides: ClassVar[dict[str, str]] = {"data": "JSON"}


class FinancialRecordSchema(BaseDbSchema):
    ticker: str = Field(..., description="Ticker symbol of the asset")
    date: dt.date = Field(..., description="Filing statement reporting date")
    item: str = Field(..., description="Financial line item key/name")
    value: float | None = Field(None, description="Numerical value of the financial item")
    period_type: str = Field(..., description="Reporting period type (e.g. Annual, Quarterly)")
    updated_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="Record update timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"},
    )

    class SQLConfig:
        table_names: ClassVar[list[str]] = ["financials", "balance_sheet", "cashflow"]
        unique_constraints: ClassVar[list[list[str]]] = [["ticker", "date", "item", "period_type"]]


class StockPriceSchema(BaseDbSchema):
    ticker: str = Field(..., description="Ticker symbol of the asset")
    date: dt.datetime = Field(..., description="Datetime interval timestamp")
    open: float = Field(..., description="Opening price of the interval")
    high: float = Field(..., description="Highest price during the interval")
    low: float = Field(..., description="Lowest price during the interval")
    close: float = Field(..., description="Closing price of the interval")
    volume: int = Field(..., description="Total volume traded during the interval")
    dividends: float = Field(0.0, description="Dividends paid on this date")
    stock_splits: float = Field(0.0, description="Stock split ratio adjustment on this date")
    updated_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="Record update timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"},
    )

    class SQLConfig:
        table_name: ClassVar[str] = "prices"
        unique_constraints: ClassVar[list[list[str]]] = [["ticker", "date"]]


class ForexRateSchema(BaseDbSchema):
    symbol: str = Field(..., description="Forex cross currency symbol (e.g. USDJPY=X)")
    date: dt.date = Field(..., description="Date of the historical rate")
    rate: float = Field(..., description="Exchanged conversion close rate")
    updated_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="Record update timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"},
    )

    class SQLConfig:
        table_name: ClassVar[str] = "forex_rates"
        unique_constraints: ClassVar[list[list[str]]] = [["symbol", "date"]]


class CryptoMetadataSchema(BaseDbSchema):
    ticker: str = Field(..., description="Crypto coin ticker symbol (Primary Key)")
    circulating_supply: float | None = Field(None, description="Circulating coin supply")
    total_supply: float | None = Field(None, description="Total coin supply")
    max_supply: float | None = Field(None, description="Maximum possible coin supply limit")
    market_cap: float | None = Field(None, description="Total market capitalization in USD")
    description: str | None = Field(None, description="Brief description text of the asset")
    updated_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="Record update timestamp",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"},
    )

    class SQLConfig:
        table_name: ClassVar[str] = "crypto_metadata"
        primary_key: ClassVar[list[str]] = ["ticker"]


import types
from typing import get_args, get_origin, Union
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
        SyncStatusSchema,
        InfoSchema,
        FinancialRecordSchema,
        StockPriceSchema,
        ForexRateSchema,
        CryptoMetadataSchema,
    ]

    sql_statements = []
    markdown_sections = []
    markdown_sections.append(
        "# database_design.md\n\nThis document describes the schema of the Yahoo Finance Provider DuckDB database."
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
        # Gracefully handle write failures (e.g. read-only file systems)
        print(f"Warning: Failed to auto-update schema files: {e}")
