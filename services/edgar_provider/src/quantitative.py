import pandas as pd
from edgar import get_by_accession_number, httpclient, set_identity
from loguru import logger

# Set identity as required by SEC
set_identity("ayato-labs ayato-labs@example.com")

# Disable disk cache to follow the "No-Local-Raw-Files" policy (ADR-0004)
httpclient.CACHE_DIRECTORY = None
# Method name correction based on runtime error
if hasattr(httpclient, "close_clients"):
    httpclient.close_clients()
elif hasattr(httpclient, "close_client"):
    httpclient.close_client()


class EdgarQuantitative:
    """
    SEC提出書類から財務数値（定量データ）を抽出するクラス
    """

    @staticmethod
    def extract_facts(accession_number: str) -> pd.DataFrame:
        """
        受理番号を指定して、その書類のXBRLから財務数値を取得する
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

            # FactsView から DataFrame を取得
            df = xbrl.facts.to_dataframe()

            if df.empty:
                logger.info(f"Empty facts for filing: {accession_number}")
                return pd.DataFrame()

            return df

        except Exception as e:
            logger.error(f"Failed to extract facts for {accession_number}: {e}")
            return pd.DataFrame()
