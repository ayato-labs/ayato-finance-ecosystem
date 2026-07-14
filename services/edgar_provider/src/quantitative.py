import pandas as pd
from edgar import get_by_accession_number, httpclient, set_identity
from loguru import logger

# SECが要求するアイデンティティ（連絡先メールアドレス）の設定
set_identity("ayato-labs ayato-labs@example.com")

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

            # XBRLの全財務ファクト項目を pandas.DataFrame に一括変換
            df = xbrl.facts.to_dataframe()

            if df.empty:
                logger.info(f"Empty facts for filing: {accession_number}")
                return pd.DataFrame()

            return df

        except Exception as e:
            logger.error(f"Failed to extract facts for {accession_number}: {e}")
            return pd.DataFrame()
