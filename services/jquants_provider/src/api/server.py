from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.core.config import settings
from src.core.db import db_manager

app = FastAPI(title="J-Quants Provider API")


class TickerInfo(BaseModel):
    code: str
    name: str
    market_section: str
    sector: str


class FinancialRecord(BaseModel):
    code: str
    target_label: str
    value: float | None
    period_date: str
    fiscal_year: str
    fiscal_period: str


@app.get("/health")
def health():
    return {"status": "healthy", "source": "jquants"}


@app.get("/tickers", response_model=list[TickerInfo])
def get_tickers(limit: int = 100, offset: int = 0):
    with db_manager.connect(settings.DB_PATH, read_only=True) as conn:
        res = conn.execute(
            "SELECT code, name, market_section, sector FROM tickers LIMIT ? OFFSET ?",
            [limit, offset],
        ).fetchall()
        return [TickerInfo(code=r[0], name=r[1], market_section=r[2], sector=r[3]) for r in res]


@app.get("/financials/{code}", response_model=list[FinancialRecord])
def get_financials(code: str):
    with db_manager.connect(settings.DB_PATH, read_only=True) as conn:
        df = conn.execute(
            "SELECT * FROM company_facts WHERE LocalCode = ? ORDER BY DisclosedDate DESC", [code]
        ).df()

    if df.empty:
        raise HTTPException(status_code=404, detail="No data found")

    records = []
    labels = settings.JQUANTS_V2_LABELS
    for _, row in df.iterrows():
        for label in labels:
            if label in row and row[label] is not None:
                records.append(
                    FinancialRecord(
                        code=code,
                        target_label=label,
                        value=row[label],
                        period_date=str(row["DisclosedDate"]),
                        fiscal_year=str(row["FiscalYear"]),
                        fiscal_period=str(row["FiscalPeriod"]),
                    )
                )
    return records
