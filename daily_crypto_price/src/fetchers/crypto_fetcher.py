from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
from loguru import logger

class CryptoPriceFetcher:
    def __init__(self):
        pass

    def fetch_daily_data(self, symbol: str, days: int = 365) -> pd.DataFrame:
        """
        Fetches daily OHLCV data for a crypto symbol from Yahoo Finance.
        e.g., BTC -> BTC-USD
        """
        yf_symbol = f"{symbol}-USD" if "-" not in symbol else symbol

        logger.info(f"Fetching {days} days of data for {yf_symbol}...")
        
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        try:
            df = yf.download(yf_symbol, start=start_date, progress=False)
            if df.empty:
                logger.warning(f"No data found for {yf_symbol}")
                return pd.DataFrame()
            
            # Clean columns (Handle MultiIndex if necessary)
            # Clean columns (Handle MultiIndex if necessary)
            if isinstance(df.columns, pd.MultiIndex):
                # If yfinance returned multiple tickers (e.g. from space-separated input)
                # we just want to flatten and take the first set of columns
                df = df.stack(level=1, future_stack=True).reset_index(level=1, drop=True)
            
            df = df.reset_index()
            # Ensure standard names
            df = df.rename(columns={
                "Date": "Date", "Close": "Close", "Open": "Open", 
                "High": "High", "Low": "Low", "Volume": "Volume"
            })
            
            # Convert Date to string YYYY-MM-DD
            df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
            
            # Clean NaNs for JSON compliance
            df = df.dropna(subset=["Close"]) # Must have at least Close
            df = df.fillna(0.0) # Fill other NaNs with 0
            
            # Drop rows where Close is 0 (invalid data)
            df = df[df["Close"] > 0]
            
            return df[["Date", "Open", "High", "Low", "Close", "Volume"]]
        except Exception as e:
            logger.exception(f"Unexpected error fetching data for {yf_symbol}: {e}")
            return pd.DataFrame()

    def fetch_metadata(self, symbol: str) -> dict:
        """
        Fetches metadata (supply, market cap, description) for a crypto symbol from Yahoo Finance.
        """
        yf_symbol = f"{symbol}-USD" if "-" not in symbol else symbol

        logger.info(f"Fetching metadata for {yf_symbol}...")
        try:
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info
            
            return {
                "circulating_supply": info.get("circulatingSupply"),
                "total_supply": info.get("totalSupply"),
                "max_supply": info.get("maxSupply"),
                "market_cap": info.get("marketCap"),
                "description": info.get("description")
            }
        except Exception as e:
            logger.exception(f"Unexpected error fetching metadata for {yf_symbol}: {e}")
            return {}
