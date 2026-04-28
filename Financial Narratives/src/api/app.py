import json
import os
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.analyzer import EdgarAnalyzer
from src.api.models import AnalysisRecord, FilingRecord, StatsResponse
from src.batch_fetch import batch_fetch
from src.logging_utils import setup_logging
from src.storage import FinancialNarrativeStorage

# Logging初期化
setup_logging("api")

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

@app.get("/narratives/{ticker}/analysis", response_model=list[AnalysisRecord])
def get_narrative_analysis(ticker: str, storage: FinancialNarrativeStorage = Depends(get_storage)):
    """特定銘柄の分析結果を取得"""
    try:
        rows = storage.get_analysis_by_ticker(ticker)
        results = []
        for r in rows:
            results.append(AnalysisRecord(
                accession_number=r[0],
                ticker=r[1],
                capex_summary=r[2],
                rd_summary=r[3],
                governance_summary=r[4],
                key_quotes=json.loads(r[5]),
                sentiment_score=r[6],
                analyzed_at=r[7]
            ))
        return results
    except Exception as e:
        logger.error(f"Failed to get analysis for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def run_analysis_task(ticker: str):
    """バックグラウンドで分析を実行"""
    storage = FinancialNarrativeStorage()
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GOOGLE_API_KEY not set, cannot run analysis.")
        return

    analyzer = EdgarAnalyzer(api_key=api_key)
    filings = storage.get_filings_by_ticker(ticker)
    
    if not filings:
        logger.warning(f"No filings found for {ticker} to analyze.")
        return

    # 最新の書類を分析
    latest = filings[0]
    acc_no = json.loads(latest[4]).get("accessionNumber")
    sections = json.loads(latest[3])
    
    analysis = await analyzer.analyze_narratives(sections)
    if analysis:
        storage.save_analysis(acc_no, ticker, analysis)
        logger.success(f"Analysis completed and saved for {ticker} ({acc_no})")

@app.post("/analyze/{ticker}")
def trigger_analysis(ticker: str, background_tasks: BackgroundTasks):
    """特定銘柄の分析をバックグラウンドで開始"""
    logger.info(f"Triggering narrative analysis for {ticker} via API")
    background_tasks.add_task(run_analysis_task, ticker.upper())
    return {"message": f"Analysis started for {ticker}", "status": "processing"}

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
