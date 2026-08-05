import os

import pandas as pd
from dotenv import load_dotenv
from edgar import get_by_accession_number, httpclient, set_identity
from loguru import logger

# .env ファイルから環境変数を読み込み
load_dotenv()

# SECが要求するアイデンティティ（連絡先メールアドレス）の設定
sec_identity = os.getenv("SEC_IDENTITY", "ayato-labs ayato-labs@example.com")
set_identity(sec_identity)

# Rawファイルをローカルに重複して持たせないポリシー（ADR-0004）に準拠するため、ディスクキャッシュを無効化
httpclient.CACHE_DIRECTORY = None
# 接続プールや不要なHTTPクライアントインスタンスを明示的にクローズ
if hasattr(httpclient, "close_clients"):
    httpclient.close_clients()
elif hasattr(httpclient, "close_client"):
    httpclient.close_client()


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
            # edgartoolsライブラリを使用して受付番号から書類を取得
            filing = get_by_accession_number(accession_number)
            if not filing:
                logger.warning(f"Filing not found for accession number: {accession_number}")
                return pd.DataFrame()

            # 書類からXBRL（構造化数値データマスタ）を抽出
            xbrl = filing.xbrl()
            if not xbrl:
                logger.info(f"No XBRL data for filing: {accession_number}")
                return pd.DataFrame()

            # XBRLの全財務ファクト項目を pandas.DataFrame に変換
            # edgartools query API で利用可能なカラムを使用
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

            # unit_ref から通貨(currency)を抽出
            def get_currency(unit_ref):
                if not unit_ref or not xbrl.units:
                    return None
                unit_info = xbrl.units.get(unit_ref)
                if unit_info and unit_info.get("type") == "simple":
                    measure = unit_info.get("measure", "")
                    if measure.startswith("iso4217:"):
                        return measure.replace("iso4217:", "")
                return None

            df["currency"] = df["unit_ref"].apply(get_currency)

            # fiscal_period を period_type と期間長から導出
            # period_type: 'instant' (時点) または 'duration' (期間)
            # duration の場合、期間長で四半期(Q1/Q2/Q3)か通期(FY)を判定
            df["period_start"] = pd.to_datetime(df["period_start"], errors="coerce")
            df["period_end"] = pd.to_datetime(df["period_end"], errors="coerce")
            df["period_instant"] = pd.to_datetime(df["period_instant"], errors="coerce")

            # duration の場合のみ期間長を計算
            duration_mask = df["period_type"] == "duration"
            df.loc[duration_mask, "period_length"] = (
                df.loc[duration_mask, "period_end"] - df.loc[duration_mask, "period_start"]
            ).dt.days

            def derive_fiscal_period(row):
                if row["period_type"] == "instant":
                    return "FY"  # 時点情報は通期として扱う
                length = row.get("period_length")
                if pd.isna(length):
                    return None

                # period_end の月から四半期を判定（より正確）
                period_end = row.get("period_end")
                if pd.notna(period_end) and hasattr(period_end, "month"):
                    month = period_end.month
                    if month in [1, 2, 3]:
                        return "Q1"
                    elif month in [4, 5, 6]:
                        return "Q2"
                    elif month in [7, 8, 9]:
                        return "Q3"
                    else:  # 10, 11, 12
                        return "FY"

                # フォールバック: 期間長で判定
                if length <= 100:  # ~3ヶ月
                    return "Q1"
                elif length <= 200:  # ~6ヶ月
                    return "Q2"
                elif length <= 300:  # ~9ヶ月
                    return "Q3"
                else:
                    return "FY"

            df["fiscal_period"] = df.apply(derive_fiscal_period, axis=1)

            # unit カラムを unit_ref + currency で構成
            df["unit"] = df["unit_ref"].fillna("") + " " + df["currency"].fillna("")
            df["unit"] = df["unit"].str.strip()
            df.loc[df["unit"] == "", "unit"] = None

            # 不要な一時カラムを削除
            df = df.drop(columns=["period_length", "period_type", "unit_ref", "currency"])

            return df

        except Exception as e:
            logger.error(f"Failed to extract facts for {accession_number}: {e}")
            return pd.DataFrame()
