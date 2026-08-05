"""Unit tests for database schema module."""

import tempfile
from pathlib import Path

from src.db_schema import (
    CompanyFactSchema,
    FilingSchema,
    FilingSectionSchema,
    generate_schema_files,
    resolve_sql_type,
)


class TestDbSchema:
    """db_schema モジュールのユニットテスト。"""

    def test_resolve_sql_type_string(self):
        """文字列型のSQL型解決テスト。"""
        assert resolve_sql_type(str, "test") == "VARCHAR"

    def test_resolve_sql_type_int(self):
        """整数型のSQL型解決テスト。"""
        assert resolve_sql_type(int, "test") == "BIGINT"

    def test_resolve_sql_type_float(self):
        """浮動小数点型のSQL型解決テスト。"""
        assert resolve_sql_type(float, "test") == "DOUBLE"

    def test_resolve_sql_type_datetime(self):
        """日時型のSQL型解決テスト。"""
        import datetime as dt

        assert resolve_sql_type(dt.datetime, "test") == "TIMESTAMP"

    def test_resolve_sql_type_date(self):
        """日付型のSQL型解決テスト。"""
        import datetime as dt

        assert resolve_sql_type(dt.date, "test") == "DATE"

    def test_resolve_sql_type_bool(self):
        """ブール型のSQL型解決テスト。"""
        assert resolve_sql_type(bool, "test") == "BOOLEAN"

    def test_resolve_sql_type_optional(self):
        """Optional型のSQL型解決テスト。"""
        assert resolve_sql_type(str | None, "test") == "VARCHAR"

    def test_resolve_sql_type_override(self):
        """型オーバーライドのテスト。"""
        overrides = {"metadata": "JSON"}
        assert resolve_sql_type(str, "metadata", overrides) == "JSON"

    def test_filing_schema_fields(self):
        """FilingSchemaのフィールド定義テスト。"""
        schema = FilingSchema(
            accession_number="0001234567-26-000001",
            ticker="AAPL",
            form="10-K",
        )
        assert schema.accession_number == "0001234567-26-000001"
        assert schema.ticker == "AAPL"
        assert schema.form == "10-K"

    def test_filing_section_schema_fields(self):
        """FilingSectionSchemaのフィールド定義テスト。"""
        schema = FilingSectionSchema(
            section_id="abc123",
            accession_number="0001234567-26-000001",
            section_name="business",
            content_md="# Business\nThis is the business section.",
        )
        assert schema.section_id == "abc123"
        assert schema.section_name == "business"

    def test_company_fact_schema_fields(self):
        """CompanyFactSchemaのフィールド定義テスト。"""
        schema = CompanyFactSchema(
            fact_id="def456",
            accession_number="0001234567-26-000001",
            ticker="AAPL",
            concept="us-gaap:Revenue",
            value=1000000.0,
        )
        assert schema.fact_id == "def456"
        assert schema.concept == "us-gaap:Revenue"
        assert schema.value == 1000000.0

    def test_generate_schema_files(self):
        """スキーマファイル生成のテスト。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            generate_schema_files(output_dir)

            # ファイルが生成されたことを確認
            assert (output_dir / "schema.sql").exists()
            assert (output_dir / "database_design.md").exists()

            # SQLファイルの内容確認
            sql_content = (output_dir / "schema.sql").read_text()
            assert "CREATE TABLE IF NOT EXISTS" in sql_content
            assert "filings" in sql_content
            assert "filing_sections" in sql_content
            assert "company_facts" in sql_content

            # Markdownファイルの内容確認
            md_content = (output_dir / "database_design.md").read_text(encoding="utf-8")
            assert "# database_design.md" in md_content
            assert "Table:" in md_content
