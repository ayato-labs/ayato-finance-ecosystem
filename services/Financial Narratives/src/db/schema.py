from dataclasses import dataclass
from typing import Dict, List

@dataclass
class Column:
    name: str
    type: str
    description: str
    is_primary_key: bool = False
    default: str = None

@dataclass
class Table:
    name: str
    columns: List[Column]
    description: str

# --- SSoT: Schema Definition ---
TABLES: Dict[str, Table] = {
    "filings": Table(
        name="filings",
        description="提出書類の生データおよびパースされた定性情報を保存するテーブル",
        columns=[
            Column("accession_number", "VARCHAR", "書類固有の受付番号 (SEC/EDINET共通)", is_primary_key=True),
            Column("ticker", "VARCHAR", "銘柄ティッカーまたは証券コード"),
            Column("cik", "VARCHAR", "SEC固有の企業識別番号 (米国株のみ)"),
            Column("form", "VARCHAR", "書類の種類 (10-K, 10-Q, 有価証券報告書など)"),
            Column("filing_date", "DATE", "書類の提出日"),
            Column("sections", "JSON", "パースされたセクション情報 (JSON形式)"),
            Column("metadata", "JSON", "補足的なメタデータ (JSON形式)"),
            Column("updated_at", "TIMESTAMP", "レコードの最終更新日時", default="CURRENT_TIMESTAMP"),
        ]
    ),
    "structured_data": Table(
        name="structured_data",
        description="LLMによって構造化された事実情報を保存するテーブル",
        columns=[
            Column("accession_number", "VARCHAR", "紐付け用の受付番号", is_primary_key=True),
            Column("ticker", "VARCHAR", "銘柄ティッカーまたは証券コード"),
            Column("structured_facts", "JSON", "AIが抽出した構造化事実 (JSON形式)"),
            Column("updated_at", "TIMESTAMP", "AI処理の最終更新日時", default="CURRENT_TIMESTAMP"),
        ]
    ),
    "schema_migrations": Table(
        name="schema_migrations",
        description="スキーマのバージョン管理用テーブル",
        columns=[
            Column("version", "INTEGER", "スキーマバージョン番号", is_primary_key=True),
            Column("applied_at", "TIMESTAMP", "適用日時", default="CURRENT_TIMESTAMP"),
            Column("description", "VARCHAR", "変更内容の説明"),
        ]
    )
}

# 現状のスキーマバージョン
CURRENT_SCHEMA_VERSION = 1

def get_create_table_sql(table_name: str) -> str:
    """テーブル定義からCREATE TABLE文を生成する"""
    table = TABLES[table_name]
    cols = []
    for col in table.columns:
        line = f"{col.name} {col.type}"
        if col.is_primary_key:
            line += " PRIMARY KEY"
        if col.default:
            line += f" DEFAULT {col.default}"
        cols.append(line)
    
    return f"CREATE TABLE IF NOT EXISTS {table.name} (\n  " + ",\n  ".join(cols) + "\n)"
