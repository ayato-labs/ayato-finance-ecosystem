import json
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from loguru import logger

from src.batch_fetch import batch_fetch
from src.storage import FinancialNarrativeStorage
from .models import FilingRecord, SyncResponse

router = APIRouter()

def get_storage():
    return FinancialNarrativeStorage()

@router.get("/status")
def get_status(storage: FinancialNarrativeStorage = Depends(get_storage)):
    try:
        summary = storage.get_summary()
        total_filings = sum(s[1] for s in summary)
        return {
            "status": "healthy",
            "total_filings": total_filings,
            "tickers_count": len(summary),
            "summary": {s[0]: s[1] for s in summary},
        }
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

@router.get("/narratives/{ticker}", response_model=list[FilingRecord])
def get_narratives(ticker: str, storage: FinancialNarrativeStorage = Depends(get_storage)):
    try:
        rows = storage.get_filings_by_ticker(ticker)
        return [
            FilingRecord(
                accession_number=r[0],
                ticker=r[1],
                form=r[3],
                filing_date=r[4],
                sections=json.loads(r[5]),
                metadata=json.loads(r[6]),
                structured_facts=storage.get_structuring_by_ticker(ticker),
                updated_at=r[7],
            )
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Error fetching narratives: {e}")
        return []

@router.post("/sync/{ticker}", response_model=SyncResponse)
def trigger_sync(ticker: str, background_tasks: BackgroundTasks, storage: FinancialNarrativeStorage = Depends(get_storage)):
    logger.info(f"Triggering sync for {ticker} via API")
    processed_ticker = ticker if ticker.isdigit() else ticker.upper()
    background_tasks.add_task(batch_fetch, [processed_ticker], run_structuring=True)
    return {"message": f"Sync and Structuring started for {ticker}", "status": "processing"}

@router.post("/sync/all", response_model=SyncResponse)
def trigger_sync_all(background_tasks: BackgroundTasks):
    logger.info("Triggering full sync via API")
    background_tasks.add_task(batch_fetch, run_structuring=True)
    return {"message": "Full sync and structuring started", "status": "processing"}
