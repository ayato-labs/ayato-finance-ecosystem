import zstandard as zstd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from edgar_core.config import settings
from edgar_core.db import db_manager

app = FastAPI(title="EDGAR Provider API")
dctx = zstd.ZstdDecompressor()


class NarrativeResponse(BaseModel):
    ticker: str
    section_name: str
    content: str
    filed_date: str


@app.get("/tickers")
def get_tickers():
    with db_manager.connect(settings.DB_PATH, read_only=True) as conn:
        res = conn.execute("SELECT DISTINCT ticker FROM company_facts").fetchall()
        return {"tickers": [r[0] for r in res]}


@app.get("/financials/{ticker}")
def get_financials(ticker: str):
    with db_manager.connect(settings.DB_PATH, read_only=True) as conn:
        res = conn.execute(
            """
            SELECT label, value, fiscal_year, fiscal_period, filed_date, form
            FROM company_facts
            WHERE ticker = ?
            ORDER BY filed_date DESC, label
        """,
            [ticker.upper()],
        ).fetchall()

        if not res:
            raise HTTPException(status_code=404, detail="Ticker not found")

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


@app.get("/narratives/{ticker}")
def get_narratives(ticker: str, section: str = None):
    query = "SELECT section_name, content_md_zstd, filed_date FROM narratives WHERE ticker = ?"
    params = [ticker.upper()]
    if section:
        query += " AND section_name = ?"
        params.append(section)

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
