import os
import re
import time

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from src.core.logging import setup_logger

from src.engine.db_engine import CryptoDBEngine
from src.fetchers.crypto_fetcher import CryptoPriceFetcher

# Configure structured logging
setup_logger(log_dir="logs", app_name="daily_crypto_price")

app = FastAPI(title="Daily Crypto Price API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from pathlib import Path
project_root = Path(__file__).resolve().parents[2]
default_db_path = str(project_root / "data" / "crypto" / "crypto_prices.duckdb")

fetcher = CryptoPriceFetcher()
db = CryptoDBEngine(db_path=os.getenv("DATABASE_PATH", default_db_path))

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

    return {"ticker": clean_ticker, "prices": prices, "metadata": metadata}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Daily Crypto Price API")
    parser.add_argument("--api", action="store_true", help="Start the API server")
    parser.add_argument("--sync", nargs="*", help="Sync specific tickers (e.g., BTC, ETH)")
    parser.add_argument("--host", default="127.0.0.1", help="Host for the API server")
    parser.add_argument("--port", type=int, default=5012, help="Port for the API server")

    args = parser.parse_args()

    if args.sync is not None:
        tickers = args.sync if args.sync else ["BTC", "ETH", "SOL", "XRP", "BNB"]
        logger.info(f"Starting crypto sync for: {tickers}")
        for t in tickers:
            try:
                df = fetcher.fetch_daily_data(t)
                if not df.empty:
                    db.save_prices(t, df)
                meta = fetcher.fetch_metadata(t)
                if meta:
                    db.save_metadata(t, meta)
                logger.info(f"Successfully synced {t}")
                # Rate limiting buffer
                time.sleep(2)
            except Exception as e:
                logger.error(f"Failed to sync {t}: {e}")
        print("Crypto sync complete.")

    elif args.api or (not args.sync and not args.api):
        logger.info(f"Starting Crypto Price API on {args.host}:{args.port}...")
        uvicorn.run(app, host=args.host, port=args.port)
