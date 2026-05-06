import zstandard as zstd
from edgar_core.config import settings
from edgar_core.db import db_manager
from edgar_core.logging import setup_logging
from edgar_core.telemetry import trace_step
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
@trace_step(step_name="api.get_tickers")
def get_tickers():
    logger.debug("Handling /tickers request")
    try:
        with db_manager.connect(settings.DB_PATH, read_only=True) as conn:
            # Note: Using filings table as it's more reliable for ticker list
            res = conn.execute("SELECT DISTINCT ticker FROM filings").fetchall()
            return {"tickers": [r[0] for r in res]}
    except Exception as e:
        logger.error(f"Failed to fetch tickers: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching tickers")


@app.get("/financials/{ticker}")
@trace_step(step_name="api.get_financials")
def get_financials(ticker: str):
    ticker = ticker.upper()
    logger.info(f"Handling /financials/{ticker} request", extra={"ticker": ticker})
    try:
        with db_manager.connect(settings.DB_PATH, read_only=True) as conn:
            res = conn.execute(
                """
                SELECT f.ticker, c.label, c.value, c.fiscal_year, c.fiscal_period, f.filed_date, f.form
                FROM company_facts c
                JOIN filings f ON c.accession_number = f.accession_number
                WHERE f.ticker = ?
                ORDER BY f.filed_date DESC, c.label
                """,
                [ticker],
            ).fetchall()

            if not res:
                logger.warning(f"Ticker {ticker} not found in database", extra={"ticker": ticker})
                raise HTTPException(status_code=404, detail=f"Ticker {ticker} not found")

            return [
                {
                    "label": r[1],
                    "value": r[2],
                    "fiscal_year": r[3],
                    "fiscal_period": r[4],
                    "filed_date": str(r[5]),
                    "form": r[6],
                }
                for r in res
            ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch financials for {ticker}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/narratives/{ticker}")
@trace_step(step_name="api.get_narratives")
def get_narratives(ticker: str, section: str = None):
    ticker = ticker.upper()
    logger.info(
        f"Handling /narratives/{ticker} request", extra={"ticker": ticker, "section": section}
    )
    query = "SELECT section_name, content_md_zstd, filed_date FROM narratives WHERE ticker = ?"
    params = [ticker]
    if section:
        query += " AND section_name = ?"
        params.append(section)

    try:
        with db_manager.connect(settings.NARRATIVES_DB_PATH, read_only=True) as conn:
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
    except Exception as e:
        logger.error(f"Failed to fetch narratives for {ticker}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
