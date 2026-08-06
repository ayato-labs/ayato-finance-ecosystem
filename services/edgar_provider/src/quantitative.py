import os
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from edgar import get_by_accession_number, httpclient, set_identity
from loguru import logger

# .env ファイルから環境変数を読み込み
load_dotenv()

# SECが要求するアイデンティティ（連絡先メールアドレス）の設定 (.env ファイル経由)
sec_identity = os.getenv("SEC_IDENTITY")
if not sec_identity:
    logger.warning("SEC_IDENTITY is not set in environment or .env file. Please set SEC_IDENTITY in .env.")
    sec_identity = "UnknownAdmin admin@example.com"
set_identity(sec_identity)

# Rawファイルをローカルに重複して持たせないポリシー（ADR-0004）に準拠するため、ディスクキャッシュを無効化
httpclient.CACHE_DIRECTORY = None
httpclient.close_clients()


def _get_currency_from_units(unit_ref: Any, units: Any) -> str | None:
    """unit_ref から ISO4217 通貨コードを抽出します。"""
    if not unit_ref or not units:
        return None
    unit_info = units.get(unit_ref)
    if unit_info and unit_info.get("type") == "simple":
        measure = unit_info.get("measure", "")
        if measure.startswith("iso4217:"):
            return measure.replace("iso4217:", "")
    return None


def _derive_fiscal_period(row: Any) -> str | None:
    """
    period_type, period_end の月, および期間長から会計四半期 (Q1/Q2/Q3/FY) を決定します。
    """
    if row["period_type"] == "instant":
        return "FY"

    length = row.get("period_length")
    if pd.isna(length):
        return None

    # 1年（通期: 350日〜375日程度）
    if length >= 350:
        return "FY"

    # 1四半期（80日〜105日程度）
    if length <= 105:
        period_end = row.get("period_end")
        if pd.notna(period_end) and hasattr(period_end, "month"):
            month = period_end.month
            if month in (1, 2, 3, 4):
                return "Q1"
            if month in (5, 6, 7):
                return "Q2"
            if month in (8, 9, 10):
                return "Q3"
            return "Q4"
        return "Q1"

    # 半期（160日〜200日程度）
    if length <= 200:
        return "Q2"

    # 9ヶ月（250日〜290日程度）
    if length <= 290:
        return "Q3"

    return "FY"


class EdgarQuantitative:
    """
    SEC提出書類（iXBRL形式）から、売上高、当期純利益、負債などの財務数値データ（定量データ）を
    自動抽出する数値処理クラス。
    """

    @staticmethod
    def extract_facts(accession_number: str) -> pd.DataFrame:
        """
        受付番号（accessionNumber）を指定して、該当する報告書のXBRLデータから
        全財務項目（Facts）を抽出して pandas.DataFrame として返します。
        storage.py の save_facts で必要なカラムを含むように query API を使用します。
        """
        try:
            filing = get_by_accession_number(accession_number)
            if not filing:
                logger.warning(f"Filing not found for accession number: {accession_number}")
                return pd.DataFrame()

            xbrl = filing.xbrl()
            if not xbrl:
                logger.info(f"No XBRL data for filing: {accession_number}")
                return pd.DataFrame()

            df = xbrl.facts.query().to_dataframe(
                "concept",
                "label",
                "numeric_value",
                "unit_ref",
                "fiscal_year",
                "period_start",
                "period_end",
                "period_instant",
                "period_type",
            )

            if df.empty:
                logger.info(f"Empty facts for filing: {accession_number}")
                return pd.DataFrame()

            df["currency"] = df["unit_ref"].apply(
                lambda u_ref: _get_currency_from_units(u_ref, xbrl.units)
            )

            df["period_start"] = pd.to_datetime(df["period_start"], errors="coerce")
            df["period_end"] = pd.to_datetime(df["period_end"], errors="coerce")
            df["period_instant"] = pd.to_datetime(df["period_instant"], errors="coerce")

            duration_mask = df["period_type"] == "duration"
            df.loc[duration_mask, "period_length"] = (
                df.loc[duration_mask, "period_end"] - df.loc[duration_mask, "period_start"]
            ).dt.days

            df["fiscal_period"] = df.apply(_derive_fiscal_period, axis=1)

            df["unit"] = df["unit_ref"].fillna("") + " " + df["currency"].fillna("")
            df["unit"] = df["unit"].str.strip()
            df.loc[df["unit"] == "", "unit"] = None

            df = df.drop(columns=["period_length", "period_type", "unit_ref", "currency"])
            return df

        except Exception as e:
            logger.error(f"Failed to extract facts for {accession_number}: {e}")
            return pd.DataFrame()
