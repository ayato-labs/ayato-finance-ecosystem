import json

from fastapi import FastAPI, Response
from loguru import logger

from src.shared.infra.logging_config import setup_logging
from src.shared.queries.repository import DataRepository

app = FastAPI(title="EDINET Provider API")


@app.on_event("startup")
async def startup_event():
    setup_logging(service_name="api_server")
    logger.info("API Server starting up...")


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/filings/search")
async def search_filings(
    edinet_code: str | None = None,
    ticker: str | None = None,
    company_name: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    logger.info(f"Received request: /filings/search (ticker={ticker}, company_name={company_name})")
    results = DataRepository.search_filings(
        edinet_code=edinet_code,
        ticker=ticker,
        company_name=company_name,
        start_date=start_date,
        end_date=end_date,
    )
    return Response(
        content=json.dumps(results, ensure_ascii=False), media_type="application/json"
    )
