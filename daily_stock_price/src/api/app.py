import pandas as pd
from datetime import datetime

from loguru import logger
import duckdb
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.engine import MarketDataEngine
from src.fetchers.yf_fetcher import YFinanceFetcher

# Configure logging



app = FastAPI(
    title="Daily Stock Price API",
    description="High-performance financial data access layer leveraging DuckDB and Parquet",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local multi-system integration, allow all for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Engine (Using default data path)
def get_engine():
    """Dependency provider for the MarketDataEngine."""
    fetcher = YFinanceFetcher()
    return MarketDataEngine(fetcher=fetcher)

# --- Models ---
class PriceRecord(BaseModel):
    Date: datetime
    Ticker: str
    Open: float
    High: float
    Low: float
    Close: float
    Volume: int
    StockSplits: float
    SharesOutstanding: float | None
    Source: str
    LoadTimestamp: datetime

class QueryRequest(BaseModel):
    sql: str
    limit: int | None = 100

class SyncResponse(BaseModel):
    status: str
    ticker: str
    message: str | None = None

# --- Endpoints ---
from fastapi import Depends

@app.get("/")
def read_root():
    return {
        "message": "Daily Stock Price API is running",
        "endpoints": [
            "/status",
            "/prices/{ticker}",
            "/query",
            "/sync/{ticker}",
        ],
        "docs": "/docs",
    }

@app.get("/status")
async def get_status(engine: MarketDataEngine = Depends(get_engine)):
    """Returns database overview metrics using the metadata catalog."""
    try:
        stats = engine.catalog.get_stats()
        return {
            "status": "ready",
            "catalog_stats": stats,
            "last_updated": datetime.now()
        }
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/prices/{ticker}", response_model=list[PriceRecord])
def get_prices(
    ticker: str, 
    start_date: str | None = None, 
    end_date: str | None = None,
    engine: MarketDataEngine = Depends(get_engine)
):
    """Retrieves price history for a specific ticker using the deduplicated view."""
    try:
        db = duckdb.connect()
        # Get the smart view SQL from the engine
        base_sql = engine.get_synced_view(ticker)
        if not base_sql:
            raise HTTPException(status_code=404, detail=f"Ticker {ticker} not found in database.")

        # Filter by date if provided
        final_sql = f"SELECT * FROM ({base_sql})"
        where_clauses = []
        if start_date:
            where_clauses.append(f"Date >= '{start_date}'")
        if end_date:
            where_clauses.append(f"Date <= '{end_date}'")

        if where_clauses:
            final_sql += " WHERE " + " AND ".join(where_clauses)

        df = db.query(final_sql).df()
        if df.empty:
            return []

        records = df.to_dict(orient="records")
        # Replace NaN with None for JSON compliance
        return [{k: (None if pd.isna(v) else v) for k, v in r.items()} for r in records]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Price retrieval failed for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.post("/sync/{ticker}", response_model=SyncResponse)
def sync_ticker(
    ticker: str, 
    days: int | None = Query(None, description="Number of days to look back"),
    engine: MarketDataEngine = Depends(get_engine)
):
    """Triggers an on-demand synchronization for a specific ticker."""
    try:
        # Note: In a production environment, this should be an async background task
        engine.sync_ticker(ticker, lookback_days=days)
        return {"status": "success", "ticker": ticker, "message": "Manual sync completed."}
    except Exception as e:
        logger.error(f"Sync failed for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}") from e

@app.post("/query")
def run_query(request: QueryRequest, engine: MarketDataEngine = Depends(get_engine)):
    """
    Executes raw analytical SQL against the data lake.
    Use {T} placeholder for the parquet files.
    Example: SELECT Ticker, AVG(Close) FROM {T} GROUP BY Ticker
    """
    try:
        db = duckdb.connect()
        path = str(engine.base_dir / "**/*.parquet").replace("\\", "/")
        processed_sql = request.sql.replace("{T}", f"read_parquet('{path}')")

        # Enforce limit for safety
        if "limit" not in processed_sql.lower():
            processed_sql += f" LIMIT {request.limit}"

        df = db.query(processed_sql).df()
        records = df.to_dict(orient="records")
        # Replace NaN with None for JSON compliance
        clean_data = [{k: (None if pd.isna(v) else v) for k, v in r.items()} for r in records]
        return {"columns": df.columns.tolist(), "data": clean_data}
    except Exception as e:
        logger.error(f"Custom query failed: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
