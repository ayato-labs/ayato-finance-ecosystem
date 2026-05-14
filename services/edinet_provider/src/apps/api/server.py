import json
from typing import Optional

from fastapi import FastAPI, Response
from loguru import logger

from src.infra.logging_config import setup_logging
from src.queries.repository import DataRepository

app = FastAPI(title="EDINET Provider API")
repo = DataRepository()


@app.on_event("startup")
async def startup_event():
    setup_logging()
    logger.info("EDINET API Server Starting...")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "2.0.0"}


@app.get("/filings/search")
async def search_filings(
    edinet_code: Optional[str] = None,
    ticker: Optional[str] = None,
    company_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    logger.info(f"Received request: /filings/search (ticker={ticker}, company_name={company_name})")
    try:
        results = repo.search_filings(
            edinet_code=edinet_code,
            ticker=ticker,
            company_name=company_name,
            start_date=start_date,
            end_date=end_date,
        )
        content = json.dumps({"count": len(results), "data": results}, ensure_ascii=True)
        return Response(content=content, media_type="application/json")
    except Exception as e:
        logger.error(f"Error in /filings/search: {e}")
        logger.exception("Traceback for API search error")
        return Response(content=json.dumps({"error": "Internal server error"}), status_code=500)


@app.get("/filings/{doc_id}")
async def get_filing(doc_id: str):
    # This is a placeholder for actual repository-based retrieval
    return {"doc_id": doc_id, "message": "Not implemented yet"}
