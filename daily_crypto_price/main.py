import os
import re

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.engine.db_engine import CryptoDBEngine
from src.fetchers.crypto_fetcher import CryptoPriceFetcher

app = FastAPI(title="Daily Crypto Price API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

fetcher = CryptoPriceFetcher()
db = CryptoDBEngine(db_path=os.getenv("DATABASE_PATH", "crypto_prices.duckdb"))

TICKER_REGEX = re.compile(r"^[A-Z0-9\-\.\_]+$")

@app.get("/")
async def root():
    return {"message": "Daily Crypto Price API is running"}

@app.get("/prices/{ticker}")
async def get_prices(ticker: str, sync: bool = Query(False)):
    """
    Returns historical prices and metadata for a crypto ticker.
    If sync=True, it fetches latest data from Yahoo Finance first.
    """
    clean_ticker = ticker.upper().strip()
    
    # Validation
    if not TICKER_REGEX.match(clean_ticker):
        logger.warning(f"Invalid ticker format rejected: {clean_ticker}")
        raise HTTPException(status_code=400, detail="Invalid ticker format")

    logger.info(f"Request for {clean_ticker} (sync={sync})")
    
    # Standardize ticker for crypto
    clean_ticker = clean_ticker.replace("-USD", "")
    
    if sync:
        try:
            # Sync Prices
            df = fetcher.fetch_daily_data(clean_ticker)
            if not df.empty:
                db.save_prices(clean_ticker, df)
            
            # Sync Metadata
            meta = fetcher.fetch_metadata(clean_ticker)
            if meta:
                db.save_metadata(clean_ticker, meta)
                
        except Exception as e:
            logger.error(f"Sync failed for {clean_ticker}: {e}")

    prices = db.get_prices(clean_ticker)
    metadata = db.get_metadata(clean_ticker)
    
    if not prices:
        raise HTTPException(status_code=404, detail=f"Ticker {clean_ticker} not found")
    
    return {
        "ticker": clean_ticker,
        "prices": prices,
        "metadata": metadata
    }

if __name__ == "__main__":
    host = os.getenv("CRYPTO_API_HOST", "127.0.0.1")
    port = int(os.getenv("CRYPTO_API_PORT", "5012"))
    logger.info(f"Starting Crypto Price API on {host}:{port}...")
    uvicorn.run(app, host=host, port=port)
