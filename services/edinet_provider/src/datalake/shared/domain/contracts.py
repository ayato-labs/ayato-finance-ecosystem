from enum import StrEnum
from pydantic import BaseModel, Field


class IngestionStatus(StrEnum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    PARTIAL_FAIL = "PARTIAL_FAIL"
    FAILED = "FAILED"


class FiscalPeriod(StrEnum):
    FY = "FY"
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"


class DataContract(BaseModel):
    doc_id: str = Field(..., description="書類ID")
    session_id: str = Field(..., description="処理セッションID (run_id)")


class FilingMetadata(DataContract):
    """
    Registry DB (registry_db) の filings テーブルのデータ契約（スキーマ定義）。
    提出された有価証券報告書等のメタデータを格納します。
    """

    edinet_code: str | None = Field(None, description="提出者のEDINETコード")
    sec_code: str | None = Field(None, description="提出者の証券コード")
    filer_name: str | None = Field(None, description="提出者名")
    doc_description: str | None = Field(None, description="提出書類の説明")
    submit_datetime: str | None = Field(None, description="提出日時")
    form_code: str | None = Field(None, description="提出書類のフォームコード")
    doc_type_code: str | None = Field(None, description="書類種別コード (例: 120=有価証券報告書)")


class CompanyFact(DataContract):
    """
    Facts DB (facts_db) の facts テーブルのデータ契約（スキーマ定義）。
    XBRLから抽出された数値ファクトデータを格納します。
    """

    item_name: str = Field(..., description="勘定科目タグ名 (例: CurrentAssets)")
    item_value: float = Field(..., description="抽出された数値データ")
    unit: str = Field(..., description="数値の単位 (例: JPY)")
    context_id: str = Field(..., description="XBRLコンテキストID (期間や連結/単体情報)")
    fiscal_year: int = Field(..., description="会計年度")
    fiscal_period: FiscalPeriod = Field(FiscalPeriod.FY, description="会計期間 (通期/四半期)")


class NarrativeBlock(DataContract):
    """
    Narrative DB (narr_db) の narratives テーブルのデータ契約（スキーマ定義）。
    XBRLから抽出された非構造化のテキスト（事業等のリスクなど）を格納します。
    """

    section_name: str = Field(..., description="抽出セクション名 (例: business_risk)")
    content_md: str = Field(..., description="Markdown形式でパースされたテキスト本文")
