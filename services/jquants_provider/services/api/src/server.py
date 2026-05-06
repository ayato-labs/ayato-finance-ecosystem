from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import date

from src.core.config import settings
from src.core.db import db_manager

app = FastAPI(title="J-Quants Provider API", version="2.0.0")


class TickerInfo(BaseModel):
    code: str
    name: str
    market_section: Optional[str]
    sector: Optional[str]


class PriceRecord(BaseModel):
    date: date
    close: float
    volume: int
    adjustment_close: float


class FinancialRecord(BaseModel):
    disclosed_date: date
    fiscal_period: str
    net_sales: Optional[float]
    operating_profit: Optional[float]
    ordinary_profit: Optional[float]
    profit: Optional[float]
    eps: Optional[float]


@app.get("/health")
def health():
    return {"status": "healthy", "source": "jquants", "shards": "multi-duckdb"}


@app.get("/tickers", response_model=list[TickerInfo])
def get_tickers(limit: int = 100, offset: int = 0):
    with db_manager.connect(settings.JP_MASTER_DB_PATH, read_only=True) as conn:
        # Join with market_sections and sectors to get names
        query = """
            SELECT 
                t.code, 
                t.name, 
                m.name as market_section, 
                s.name as sector 
            FROM tickers t
            LEFT JOIN market_sections m ON t.market_section_id = m.id
            LEFT JOIN sectors s ON t.sector_id = s.id
            LIMIT ? OFFSET ?
        """
        res = conn.execute(query, [limit, offset]).fetchall()
        return [
            TickerInfo(code=r[0], name=r[1], market_section=r[2], sector=r[3]) 
            for r in res
        ]


@app.get("/prices/{code}", response_model=list[PriceRecord])
def get_price_history(
    code: str, 
    start_date: Optional[date] = None, 
    end_date: Optional[date] = None,
    limit: int = 1000
):
    with db_manager.connect(settings.JP_PRICES_DB_PATH, read_only=True) as conn:
        query = "SELECT Date, Close, Volume, AdjustmentClose FROM daily_prices WHERE Code = ?"
        params = [code]
        
        if start_date:
            query += " AND Date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND Date <= ?"
            params.append(end_date)
            
        query += " ORDER BY Date DESC LIMIT ?"
        params.append(limit)
        
        res = conn.execute(query, params).fetchall()
        return [
            PriceRecord(date=r[0], close=r[1], volume=r[2], adjustment_close=r[3]) 
            for r in res
        ]


@app.get("/financials/{code}", response_model=list[FinancialRecord])
def get_financial_history(code: str, limit: int = 20):
    with db_manager.connect(settings.JP_FACTS_DB_PATH, read_only=True) as conn:
        query = """
            SELECT 
                DisclosedDate, FiscalPeriod, NetSales, OperatingProfit, 
                OrdinaryProfit, Profit, EarningsPerShare 
            FROM company_facts 
            WHERE LocalCode = ? 
            ORDER BY DisclosedDate DESC 
            LIMIT ?
        """
        res = conn.execute(query, [code, limit]).fetchall()
        return [
            FinancialRecord(
                disclosed_date=r[0],
                fiscal_period=r[1],
                net_sales=r[2],
                operating_profit=r[3],
                ordinary_profit=r[4],
                profit=r[5],
                eps=r[6]
            ) 
            for r in res
        ]
