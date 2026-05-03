from fastapi import FastAPI, HTTPException

from ..engine import MacroEngine
from ..fetchers.fred_fetcher import FredFetcher


app = FastAPI(title="Macro Economic API")
engine = MacroEngine()
fetcher = FredFetcher()

@app.get("/indicators/{symbol}")
async def get_indicator(symbol: str):
    """
    指定されたマクロ指標のデータを取得する。
    """
    data = engine.get_values(symbol)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")  # noqa: PLR2004
    return data

@app.post("/sync/{symbol}")
async def sync_indicator(symbol: str):
    """
    指定されたマクロ指標のデータを同期する。
    """
    last_date = engine.get_latest_date(symbol)
    df = fetcher.fetch(symbol, last_date)

    if df.empty:
        return {"status": "skipped", "message": "No new data to sync"}

    engine.save_data(symbol, df)
    return {"status": "success", "rows_added": len(df)}

@app.get("/health")
async def health():
    return {"status": "healthy"}
