import datetime as dt
from typing import Any, ClassVar

from pydantic import BaseModel, Field

# =====================================================================
# Pydanticモデルを使用したSchema-as-Code定義
# =====================================================================

class BaseDbSchema(BaseModel):
    """
    すべてのデータベーススキーマモデルの共通基底クラス。
    Pydantic V2の仕様に基づき、エイリアスによるフィールド設定や
    カスタムオブジェクト（日時型など）の許容設定を行います。
    """
    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class FilingSchema(BaseDbSchema):
    """
    SEC提出書類のメタデータ情報（メタデータテーブル）のスキーマ定義。
    書類本文（JSON）を含まず、軽量な管理情報を格納します。
    """
    accession_number: str = Field(..., description="SEC受付番号 (プライマリキー)")
    ticker: str | None = Field(None, description="上場企業のティッカーシンボル")
    cik: str | None = Field(None, description="SEC登録企業中央インデックスキー (CIK)")
    form: str | None = Field(None, description="提出フォーム種類 (例: 10-K, 10-Q)")
    filing_date: dt.date | None = Field(None, description="SEC公式の書類提出日")
    metadata: Any = Field(None, description="JSON形式で格納されるその他付随メタデータ")
    updated_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="データベースレコード挿入/更新日時",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"},
    )

    class SQLConfig:
        table_name: ClassVar[str] = "filings"
        primary_key: ClassVar[list[str]] = ["accession_number"]
        type_overrides: ClassVar[dict[str, str]] = {"metadata": "JSON"}


class FilingSectionSchema(BaseDbSchema):
    """
    提出書類から抽出されたテキスト本文セクション（定性データテーブル）のスキーマ定義。
    1つの章（Item）ごとに1レコード（1行）としてリレーショナルに保存されます。
    """
    section_id: str = Field(..., description="セクションの一意のハッシュ値 (プライマリキー、MD5形式)")
    accession_number: str = Field(..., description="対応する提出書類の受付番号 (filingsテーブルへの外部キー)")
    section_name: str = Field(..., description="セクション章名 (例: mda, business, risk_factors)")
    content_md: str = Field(..., description="HTMLからパースおよび抽出された生のマークダウン形式テキスト本文")
    updated_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="データベースレコード挿入/更新日時",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"},
    )

    class SQLConfig:
        table_name: ClassVar[str] = "filing_sections"
        primary_key: ClassVar[list[str]] = ["section_id"]


class CompanyFactSchema(BaseDbSchema):
    """
    XBRLタグから抽出された企業の財務数値データ（定量Factsテーブル）のスキーマ定義。
    """
    fact_id: str = Field(..., description="財務数値ファクトの一意のハッシュキー (プライマリキー、MD5形式)")
    accession_number: str | None = Field(
        None, description="対応する提出書類の受付番号"
    )
    ticker: str | None = Field(None, description="企業ティッカーシンボル")
    concept: str | None = Field(None, description="XBRL標準分類項目名 (概念タグ、例: Revenue, Liabilities)")
    label: str | None = Field(None, description="会計項目の人間向けのラベル説明")
    value: float | None = Field(None, description="実際の財務指標数値 (DOUBLE型)")
    unit: str | None = Field(
        None, description="数値の単位 (例: USD, Shares)"
    )
    fiscal_year: int | None = Field(None, description="対象決算年度 (会計年度)")
    fiscal_period: str | None = Field(
        None, description="対象決算四半期 (例: FY, Q1, Q2, Q3)"
    )
    period_start: dt.date | None = Field(
        None, description="財務報告期間の開始日 (フローデータ用)"
    )
    period_end: dt.date | None = Field(
        None, description="財務報告期間の終了日 (フローデータ用)"
    )
    period_instant: dt.date | None = Field(None, description="貸借対照表などの時点指定日 (ストックデータ用)")
    updated_at: dt.datetime = Field(
        default_factory=dt.datetime.now,
        description="データベースレコード挿入/更新日時",
        json_schema_extra={"sql_default": "CURRENT_TIMESTAMP"},
    )

    class SQLConfig:
        table_name: ClassVar[str] = "company_facts"
        primary_key: ClassVar[list[str]] = ["fact_id"]


# =====================================================================
# DDL（SQL）および Markdown ドキュメント自動生成用ヘルパーロジック
# =====================================================================

import types
from pathlib import Path
from typing import Union, get_args, get_origin

# Python の型から SQL (DuckDB) のデータ型へのマッピングテーブル
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
    """
    Pydantic フィールドの型アノテーションを解釈し、対応する SQL データ型文字列を解決します。
    Union/Optional型にも再帰的に対応します。
    """
    if type_overrides and field_name in type_overrides:
        return type_overrides[field_name]

    # Optional型やUnion型 (Python 3.10以降の | 構文含む) を展開して中身を再帰判定
    origin = get_origin(field_type)
    if (
        origin is Union
        or origin == type(Union)
        or (hasattr(types, "UnionType") and origin is types.UnionType)
    ):
        args = get_args(field_type)
        # None型(Optionalの右側)を除外した実際の型アノテーションを抽出
        non_none_args = [arg for arg in args if arg is not type(None)]
        if non_none_args:
            return resolve_sql_type(non_none_args[0], field_name, type_overrides)

    if field_type in TYPE_MAPPING:
        return TYPE_MAPPING[field_type]

    # 辞書やリスト、任意型は JSON 形式として解釈
    if origin in (dict, list) or field_type is Any:
        return "JSON"

    return "VARCHAR"


def generate_schema_files(output_dir: Path):
    """
    本番データ配置ディレクトリに対して、定義された Schema-as-Code から
    1) テーブル作成用クエリ群 (schema.sql)
    2) データベース設計書 (database_design.md)
    を自動生成して書き出します。これにより設計と実装の乖離を防ぎます。
    """
    schemas = [
        FilingSchema,
        FilingSectionSchema,
        CompanyFactSchema,
    ]

    sql_statements = []
    markdown_sections = []
    markdown_sections.append(
        "# database_design.md\n\nThis document describes the schema of the SEC EDGAR Provider DuckDB database."
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

        # Pydantic フィールド群から SQL カラム宣言と MD 設計書を自動生成
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

        # ユニークキーや複合主キーの制約追加
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

    # schema.sql と database_design.md を指定フォルダに書き出し
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "schema.sql").write_text("\n\n".join(sql_statements) + "\n", encoding="utf-8")
        (output_dir / "database_design.md").write_text(
            "\n".join(markdown_sections) + "\n", encoding="utf-8"
        )
    except Exception as e:
        print(f"Warning: Failed to auto-update SEC EDGAR schema files: {e}")
