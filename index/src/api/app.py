from loguru import logger
from fastapi import FastAPI, HTTPException
from ..engine import IndexEngine
from ..fetchers.yf_fetcher import YFinanceFetcher
from datetime import datetime


app = FastAPI(title="Market Index API")
engine = IndexEngine()
fetcher = YFinanceFetcher()

@app.get("/prices/{ticker}")
async def get_prices(ticker: str):
    """
    指定された指数の価格データを取得する。
    """
    data = engine.get_prices(ticker)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data found for {ticker}")
    return data

@app.post("/sync/{ticker}")
async def sync_ticker(ticker: str):
    """
    指定された指数のデータを同期する。
    """
    last_date = engine.get_latest_date(ticker)
    df = fetcher.fetch(ticker, last_date)
    
    if df.empty:
        return {"status": "skipped", "message": "No new data to sync"}
        
    engine.save_data(ticker, df)
    return {"status": "success", "rows_added": len(df)}

@app.get("/health")
async def health():
    return {"status": "healthy"}
