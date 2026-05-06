import zstandard as zstd
from edgar_core.config import settings
from edgar_core.db import db_manager
from edgar_core.logging import setup_logging
from fastapi import FastAPI, HTTPException
from loguru import logger
from pydantic import BaseModel

# Initialize logging on startup
setup_logging()

app = FastAPI(title="EDGAR Provider API")
dctx = zstd.ZstdDecompressor()


class NarrativeResponse(BaseModel):
    ticker: str
    section_name: str
    content: str
    filed_date: str


@app.get("/tickers")
def get_tickers():
    logger.debug("Handling /tickers request")
    try:
        with db_manager.connect(settings.DB_PATH, read_only=True) as conn:
            res = conn.execute("SELECT DISTINCT ticker FROM company_facts").fetchall()
            return {"tickers": [r[0] for r in res]}
    except Exception as e:
        logger.error(f"Failed to fetch tickers: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching tickers")


@app.get("/financials/{ticker}")
def get_financials(ticker: str):
    ticker = ticker.upper()
    logger.info("Handling /financials/{{ticker}} request", extra={"ticker": ticker})
    try:
        with db_manager.connect(settings.DB_PATH, read_only=True) as conn:
            res = conn.execute(
                """
                SELECT label, value, fiscal_year, fiscal_period, filed_date, form
                FROM company_facts
                WHERE ticker = ?
                ORDER BY filed_date DESC, label
                """,
                [ticker],
            ).fetchall()

            if not res:
                logger.warning("Ticker {{ticker}} not found in database", extra={"ticker": ticker})
                raise HTTPException(status_code=404, detail=f"Ticker {ticker} not found")

            return [
                {
                    "label": r[0],
                    "value": r[1],
                    "fiscal_year": r[2],
                    "fiscal_period": r[3],
                    "filed_date": str(r[4]),
                    "form": r[5],
                }
                for r in res
            ]
    except HTTPException:
        raise
    except Exception:
        logger.error("Failed to fetch financials for {ticker}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/narratives/{ticker}")
def get_narratives(ticker: str, section: str = None):
    ticker = ticker.upper()
    logger.info(
        "Handling /narratives/{ticker} request", extra={"ticker": ticker, "section": section}
    )
    query = "SELECT section_name, content_md_zstd, filed_date FROM narratives WHERE ticker = ?"
    params = [ticker]
    if section:
        query += " AND section_name = ?"
        params.append(section)

    try:
        with db_manager.connect(settings.DB_PATH, read_only=True) as conn:
            res = conn.execute(query, params).fetchall()

            return [
                NarrativeResponse(
                    ticker=ticker,
                    section_name=r[0],
                    content=dctx.decompress(r[1]).decode("utf-8"),
                    filed_date=str(r[2]),
                )
                for r in res
            ]
    except Exception:
        logger.error("Failed to fetch narratives for {ticker}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
