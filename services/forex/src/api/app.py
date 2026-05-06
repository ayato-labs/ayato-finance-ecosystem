from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ..engine import ForexEngine
from ..fetchers.forex_fetcher import ForexFetcher

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


def get_engine():
    return ForexEngine()


@app.get("/rates/{symbol}")
async def get_rates(symbol: str, engine: Annotated[ForexEngine, Depends(get_engine)]):
    """
    指定された通貨の対米ドルレート(1 Unit = X USD)の履歴を取得する。
    """
    symbol = symbol.upper()
    data = engine.get_rates(symbol)
    if not data and symbol != "USD":
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")

    # ... (rest of logic)
    if symbol == "USD":
        return [{"Date": datetime.now().strftime("%Y-%m-%d"), "Symbol": "USD", "Rate": 1.0}]
    return data


@app.get("/latest/{symbol}")
async def get_latest_rate(symbol: str, engine: Annotated[ForexEngine, Depends(get_engine)]):
    """
    最新の為替レートを取得する。
    """
    symbol = symbol.upper()
    rate = engine.get_latest_rate(symbol)
    if rate is None:
        raise HTTPException(status_code=404, detail=f"No rate found for {symbol}")
    return {"symbol": symbol, "rate": rate}


@app.post("/sync/{symbol}")
async def sync_forex(symbol: str, engine: Annotated[ForexEngine, Depends(get_engine)]):
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
