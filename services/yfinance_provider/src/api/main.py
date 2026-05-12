import json
import os

import uvicorn
from fastapi import FastAPI, HTTPException

from ..core.db_manager import DatabaseManager
from ..core.logger import setup_logger

logger = setup_logger("api_server")
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "yfinance.duckdb")

app = FastAPI(title="yfinance Local Mirror API")
db_manager = DatabaseManager(DB_PATH)


@app.get("/health")
def health():
    return {"status": "healthy", "db": DB_PATH}


@app.get("/tickers/{ticker}/info")
def get_ticker_info(ticker: str):
    conn = db_manager.get_connection()
    res = conn.execute("SELECT data FROM info WHERE ticker = ?", [ticker]).fetchone()
    conn.close()
    if not res:
        raise HTTPException(status_code=404, detail="Ticker info not found locally")
    return json.loads(res[0])


@app.get("/tickers/{ticker}/financials")
def get_financials(ticker: str, period: str = "Annual"):
    conn = db_manager.get_connection()
    df = conn.execute(
        """
        SELECT date, item, value FROM financials
        WHERE ticker = ? AND period_type = ?
        ORDER BY date DESC
    """,
        [ticker, period],
    ).df()
    conn.close()
    if df.empty:
        raise HTTPException(status_code=404, detail="Financials not found locally")
    return df.to_dict(orient="records")


@app.get("/sync/status")
def get_sync_status():
    conn = db_manager.get_connection()
    df = conn.execute("SELECT * FROM sync_status ORDER BY updated_at DESC LIMIT 100").df()
    conn.close()
    return df.to_dict(orient="records")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5015)
