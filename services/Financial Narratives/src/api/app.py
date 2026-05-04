import json
from typing import Annotated

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

load_dotenv()

from src.api.models import FilingRecord, StatsResponse
from src.batch_fetch import batch_fetch
from src.db.master_db import JobQueue
from src.logging_utils import setup_logging
from src.storage import FinancialNarrativeStorage

# Logging初期化
setup_logging("api")

app = FastAPI(
    title="Financial Narratives API",
    description="Qualitative data extraction service for SEC filings (MD&A, Risk Factors, etc.)",
    version="1.0.0",
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


def get_queue():
    return JobQueue()


@app.get("/")
def read_root():
    return {
        "service": "Financial Narratives API",
        "endpoints": [
            "/status",
            "/narratives/{ticker}",
            "/analysis/{ticker}",
            "/sync/{ticker}",
            "/reconcile",
        ],
        "docs": "/docs",
    }


@app.get("/status", response_model=StatsResponse)
def get_status(
    storage: Annotated[FinancialNarrativeStorage, Depends(get_storage)],
    queue: Annotated[JobQueue, Depends(get_queue)],
):
    """DBとパイプラインのステータスを取得"""
    try:
        stats = storage.get_stats()
        stats["pipeline_stats"] = queue.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/analysis/{ticker}")
def get_analysis(
    ticker: str, storage: Annotated[FinancialNarrativeStorage, Depends(get_storage)]
):
    """特定銘柄の構造化済みAI分析データを取得"""
    try:
        data = storage.get_structuring_by_ticker(ticker)
        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"No structured analysis found for {ticker}. It might be in the queue.",
            )
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get analysis for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/narratives/{ticker}", response_model=list[FilingRecord])
def get_narratives(
    ticker: str, storage: Annotated[FinancialNarrativeStorage, Depends(get_storage)]
):
    """特定銘柄の定性データを全て取得"""
    try:
        rows = storage.get_filings_by_ticker(ticker)
        if not rows:
            return []

        results = []
        for r in rows:
            results.append(
                FilingRecord(
                    ticker=r[0],
                    form=r[1],
                    filing_date=r[2],
                    sections=json.loads(r[3]),
                    metadata=json.loads(r[4]),
                    structured_facts=storage.get_structuring_by_ticker(ticker),
                    updated_at=r[5],
                    accession_number=json.loads(r[4]).get("accessionNumber", "unknown"),
                )
            )
        return results
    except Exception as e:
        logger.error(f"Failed to get narratives for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/sync/{ticker}")
def trigger_sync(ticker: str, background_tasks: BackgroundTasks):
    """特定銘柄の同期をバックグラウンドで開始"""
    logger.info(f"Triggering sync for {ticker} via API")
    # 数字の場合はそのまま、英字の場合は大文字にする
    processed_ticker = ticker if ticker.isdigit() else ticker.upper()
    background_tasks.add_task(batch_fetch, [processed_ticker], run_structuring=True)
    return {"message": f"Sync and Structuring started for {ticker}", "status": "processing"}


@app.post("/sync/all")
def trigger_sync_all(background_tasks: BackgroundTasks):
    """全銘柄の同期と構造化をバックグラウンドで開始"""
    logger.info("Triggering full sync via API")
    background_tasks.add_task(batch_fetch, run_structuring=True)
    return {"message": "Full sync and structuring started", "status": "processing"}


@app.post("/reconcile")
def trigger_reconcile(background_tasks: BackgroundTasks):
    """DB間の不整合（未構造化データ）を検知し、ジョブキューを更新"""
    from src.reconciler import Reconciler

    def run_reconcile():
        reconciler = Reconciler()
        reconciler.run()

    logger.info("Triggering Reconciler via API")
    background_tasks.add_task(run_reconcile)
    return {"message": "Reconciliation started", "status": "processing"}
