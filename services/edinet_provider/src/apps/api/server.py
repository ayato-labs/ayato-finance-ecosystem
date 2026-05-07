from fastapi import FastAPI
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

@app.get("/filings/{doc_id}")
async def get_filing(doc_id: str):
    # This is a placeholder for actual repository-based retrieval
    return {"doc_id": doc_id, "message": "Not implemented yet"}
