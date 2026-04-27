import json
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from ..storage import FinancialNarrativeStorage
from ..batch_fetch import batch_fetch
from .models import FilingRecord, StatsResponse

app = FastAPI(
    title="Financial Narratives API",
    description="Qualitative data extraction service for SEC filings (MD&A, Risk Factors, etc.)",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_storage():
    return FinancialNarrativeStorage()

@app.get("/")
def read_root():
    return {
        "service": "Financial Narratives API",
        "endpoints": ["/status", "/narratives/{ticker}", "/sync/{ticker}"],
        "docs": "/docs"
    }

@app.get("/status", response_model=StatsResponse)
def get_status(storage: FinancialNarrativeStorage = Depends(get_storage)):
    """DBのサマリー統計を取得"""
    try:
        return storage.get_stats()
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/narratives/{ticker}", response_model=list[FilingRecord])
def get_narratives(ticker: str, storage: FinancialNarrativeStorage = Depends(get_storage)):
    """特定銘柄の定性データを全て取得"""
    try:
        rows = storage.get_filings_by_ticker(ticker)
        if not rows:
            return []
            
        results = []
        for r in rows:
            results.append(FilingRecord(
                ticker=r[0],
                form=r[1],
                filing_date=r[2],
                sections=json.loads(r[3]),
                metadata=json.loads(r[4]),
                updated_at=r[5],
                accession_number=json.loads(r[4]).get("accessionNumber", "unknown")
            ))
        return results
    except Exception as e:
        logger.error(f"Failed to get narratives for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sync/{ticker}")
def trigger_sync(ticker: str, background_tasks: BackgroundTasks):
    """特定銘柄の同期をバックグラウンドで開始"""
    logger.info(f"Triggering sync for {ticker} via API")
    background_tasks.add_task(batch_fetch, [ticker.upper()])
    return {"message": f"Sync started for {ticker}", "status": "processing"}

@app.post("/sync/all")
def trigger_sync_all(background_tasks: BackgroundTasks):
    """全銘柄の同期をバックグラウンドで開始"""
    logger.info("Triggering full sync via API")
    background_tasks.add_task(batch_fetch)
    return {"message": "Full sync started", "status": "processing"}
