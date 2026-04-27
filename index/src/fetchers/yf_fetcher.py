from datetime import datetime
import pandas as pd
import yfinance as yf
from loguru import logger
from ..schema import enforce_schema

class YFinanceFetcher:
    """
    Yahoo Finance (yfinance) を使用して指数データを取得するフェッチャー。
    """
    @property
    def source_name(self) -> str:
        return "yfinance"

    def fetch(self, ticker: str, start_date: datetime) -> pd.DataFrame:
        """
        指定されたティッカーのデータを開始日から現在まで取得する。
        """
        logger.info(f"Downloading {ticker} via yfinance starting from {start_date.date()}...")
        try:
            # 指数はactions=True（配当など）は基本不要だが一貫性のために設定可能
            df = yf.download(
                ticker, 
                start=start_date.strftime("%Y-%m-%d"), 
                progress=False
            )
            
            if df.empty:
                logger.warning(f"yfinance returned empty data for {ticker}")
                return pd.DataFrame()

            # MultiIndex のフラット化 (単一銘柄でも階層化される場合があるため)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            return enforce_schema(df, ticker, self.source_name)
        except Exception as e:
            logger.error(f"yfinance error during fetch for {ticker}: {e}")
            return pd.DataFrame()
