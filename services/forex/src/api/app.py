from loguru import logger
from fastapi import FastAPI, HTTPException
from ..engine import ForexEngine
from ..fetchers.forex_fetcher import ForexFetcher
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="Forex API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = ForexEngine()
fetcher = ForexFetcher()

@app.get("/rates/{symbol}")
async def get_rates(symbol: str):
    """
    指定された通貨の対米ドルレート(1 Unit = X USD)の履歴を取得する。
    """
    symbol = symbol.upper()
    data = engine.get_rates(symbol)
    if not data and symbol != "USD":
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
    
    if symbol == "USD":
        # Dynamic response for USD
        import pandas as pd
        from datetime import datetime
        return [{"Date": datetime.now().strftime("%Y-%m-%d"), "Symbol": "USD", "Rate": 1.0}]
        
    return data

@app.get("/latest/{symbol}")
async def get_latest_rate(symbol: str):
    """
    最新の為替レートを取得する。
    """
    symbol = symbol.upper()
    rate = engine.get_latest_rate(symbol)
    if rate is None:
        raise HTTPException(status_code=404, detail=f"No rate found for {symbol}")
    return {"symbol": symbol, "rate": rate}

@app.post("/sync/{symbol}")
async def sync_forex(symbol: str):
    """
    為替データを同期する。
    """
    symbol = symbol.upper()
    last_date = engine.get_latest_date(symbol)
    df = fetcher.fetch(symbol, last_date)
    
    if df.empty:
        return {"status": "skipped", "message": "No new data to sync"}
        
    engine.save_data(symbol, df)
    return {"status": "success", "rows_added": len(df)}

@app.get("/health")
async def health():
    return {"status": "healthy"}
