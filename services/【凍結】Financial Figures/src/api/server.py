import os
import threading
import time
from contextlib import asynccontextmanager, contextmanager

from fastapi import FastAPI, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from src.core.config import settings
from src.core.db import db_manager
from src.core.logging import setup_logging
from src.providers.edinet.sync_worker import EDINETSyncWorker
from src.services.market_sync import BatchSyncService

# Initialize logging
setup_logging()


def run_background_sync(service: BatchSyncService):
    """Run incremental sync in the background."""
    if os.getenv("DISABLE_AUTO_SYNC", "false").lower() == "true":
        logger.info("Background sync is disabled via environment variable.")
        return

    try:
        logger.info("Starting background incremental sync for all markets...")
        service.sync_market_full("US", incremental=True)
        service.sync_market_full("JP", incremental=True)
        logger.info("Background incremental sync completed.")
    except Exception as e:
        logger.error(f"Background sync failed: {e}")


# Create a global sync service instance
# We start workers here so they are available for the lifetime of the process
sync_service = BatchSyncService(start_workers=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Only start sync thread if not disabled
    if os.getenv("DISABLE_AUTO_SYNC", "false").lower() != "true":
        sync_thread = threading.Thread(
            target=run_background_sync, args=(sync_service,), daemon=True
        )
        sync_thread.start()
    yield
    # Safely stop background workers on shutdown
    sync_service.stop()


app = FastAPI(
    title="Financial Figures Unified API",
    description=(
        "A production-grade unified financial database API "
        "serving standardized US and Japan market data."
    ),
    version="0.2.1",
    lifespan=lifespan,
)


class DBManager:
    def __init__(self):
        settings.DB_PATH_US.parent.mkdir(parents=True, exist_ok=True)
        settings.DB_PATH_JP.parent.mkdir(parents=True, exist_ok=True)
        settings.DB_PATH_TRACEABILITY.parent.mkdir(parents=True, exist_ok=True)
        self.read_only = os.getenv("DB_READ_ONLY", "false").lower() == "true"
        if self.read_only:
            logger.info("Operating in READ_ONLY mode (Standardized Manager).")

    @contextmanager
    def get_us_conn(self):
        with db_manager.connect(settings.DB_PATH_US, read_only=self.read_only) as conn:
            yield conn

    @contextmanager
    def get_jp_conn(self):
        with db_manager.connect(settings.DB_PATH_JP, read_only=self.read_only) as conn:
            yield conn

    @contextmanager
    def get_audit_conn(self):
        with db_manager.connect(settings.DB_PATH_TRACEABILITY, read_only=self.read_only) as conn:
            yield conn

    @contextmanager
    def get_edinet_conn(self):
        with db_manager.connect(settings.DB_PATH_EDINET, read_only=self.read_only) as conn:
            yield conn


db = DBManager()


class FinancialRecord(BaseModel):
    market: str = Field(..., json_schema_extra={"example": "US"})
    symbol: str = Field(..., json_schema_extra={"example": "AAPL"})
    company_name: str = Field(..., json_schema_extra={"example": "Apple Inc."})
    target_label: str = Field(..., json_schema_extra={"example": "NetIncome"})
    value: float = Field(..., json_schema_extra={"example": 1000000.0})
    unit: str = Field(..., json_schema_extra={"example": "USD"})
    period_date: str = Field(..., json_schema_extra={"example": "2023-12-31"})
    fiscal_year: int | None = Field(None, json_schema_extra={"example": 2023})
    reasoning: str | None = Field(None, description="AI reasoning for map decision")


class TickerInfo(BaseModel):
    market: str
    symbol: str
    name: str


class Stats(BaseModel):
    us_tickers: int
    jp_tickers: int
    us_facts: int
    jp_facts: int
    total_sync_sessions: int


@app.get("/health", tags=["System"])
def health_check():
    """Check database connectivity."""
    try:
        with db.get_us_conn() as conn:
            conn.execute("SELECT 1")
        with db.get_jp_conn() as conn:
            conn.execute("SELECT 1")
        with db.get_audit_conn() as conn:
            conn.execute("SELECT 1")
        return {"status": "healthy", "databases": ["us", "jp", "audit"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/stats", response_model=Stats, tags=["System"])
def get_stats():
    """Get database statistics (counts per market)."""
    us_t, us_f, jp_t, jp_f, sessions = 0, 0, 0, 0, 0
    try:
        with db.get_us_conn() as conn:
            us_t = conn.execute("SELECT count(*) FROM tickers").fetchone()[0]
            us_f = conn.execute("SELECT count(*) FROM company_facts").fetchone()[0]
    except Exception as e:
        logger.error(f"Failed to fetch US stats: {e}")

    try:
        with db.get_jp_conn() as conn:
            jp_t = conn.execute("SELECT count(*) FROM tickers").fetchone()[0]
            jp_f = conn.execute("SELECT count(*) FROM company_facts").fetchone()[0]
        with db.get_edinet_conn() as conn:
            edinet_f = conn.execute("SELECT count(*) FROM company_facts").fetchone()[0]
            jp_f += edinet_f
    except Exception as e:
        logger.error(f"Failed to fetch JP/EDINET stats: {e}")

    try:
        with db.get_audit_conn() as conn:
            sessions = conn.execute("SELECT count(*) FROM sync_sessions").fetchone()[0]
    except Exception as e:
        logger.error(f"Failed to fetch session stats: {e}")

    return Stats(
        us_tickers=us_t,
        jp_tickers=jp_t,
        us_facts=us_f,
        jp_facts=jp_f,
        total_sync_sessions=sessions,
    )


@app.get("/tickers", response_model=list[TickerInfo], tags=["Market Data"])
def get_tickers(
    market: str | None = Query(None, pattern="^(US|JP|us|jp)$"),
    search: str | None = Query(None, min_length=1),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """List tickers with optional market filter, search, and pagination."""
    results = []

    us_query = "SELECT 'US' as market, ticker as symbol, name FROM tickers"
    jp_query = "SELECT 'JP' as market, code as symbol, name FROM tickers"

    if market:
        market = market.upper()

    search_cond = " WHERE (symbol ILIKE ? OR name ILIKE ?)" if search else ""
    search_params = [f"%{search}%", f"%{search}%"] if search else []

    try:
        if not market or market == "US":
            q = us_query
            if search:
                q += search_cond.replace("symbol", "ticker")
            with db.get_us_conn() as conn:
                us_res = conn.execute(q, search_params).fetchall()
                results.extend([TickerInfo(market=r[0], symbol=r[1], name=r[2]) for r in us_res])
    except Exception as e:
        logger.error(f"Error fetching US tickers: {e}")

    try:
        if not market or market == "JP":
            q = jp_query
            if search:
                q += search_cond.replace("symbol", "code")
            with db.get_jp_conn() as conn:
                jp_res = conn.execute(q, search_params).fetchall()
                results.extend([TickerInfo(market=r[0], symbol=r[1], name=r[2]) for r in jp_res])
    except Exception as e:
        logger.error(f"Error fetching JP tickers: {e}")

    # Sort and paginate in Python since we combined two DBs
    results.sort(key=lambda x: x.symbol)
    return results[offset : offset + limit]


@app.get("/financials/{symbol}", response_model=list[FinancialRecord], tags=["Market Data"])
def get_financials(
    symbol: str, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)
):
    """Retrieve standardized financials for a symbol with pagination."""
    symbol = symbol.upper()
    jp_ticker_len = 4
    is_jp = symbol.isdigit() and len(symbol) == jp_ticker_len
    market = "JP" if is_jp else "US"

    records = []

    try:
        if is_jp:
            # 1. Fetch from J-Quants Native Table (Wide Format)
            query = """
                SELECT f.*, t.name
                FROM company_facts f
                JOIN tickers t ON f.LocalCode = t.code
                WHERE f.LocalCode = ?
            """
            with db.get_jp_conn() as conn:
                facts_df = conn.execute(query, [symbol]).df()

            if not facts_df.empty:
                company_name = facts_df["name"].iloc[0]
                # Map wide columns to standard labels
                standard_labels = settings.JQUANTS_V2_LABELS
                for _, row in facts_df.iterrows():
                    for label in standard_labels:
                        if label in row and row[label] is not None and str(row[label]) != "":
                            try:
                                val = float(row[label])
                                record = FinancialRecord(
                                    market="JP",
                                    symbol=symbol,
                                    company_name=company_name,
                                    target_label=label,
                                    value=val,
                                    unit="JPY",
                                    period_date=str(row["DisclosedDate"]),
                                    fiscal_year=(
                                        int(row["FiscalYear"]) if row["FiscalYear"] else None
                                    ),
                                    reasoning="Direct J-Quants Native Mapping",
                                )
                                records.append(record)
                            except (ValueError, TypeError):
                                continue

            # 2. FALLBACK: Try EDINET DB for additional history/tags
            try:
                edinet_query = """
                    SELECT *
                    FROM company_facts
                    WHERE LocalCode = ?
                """
                with db.get_edinet_conn() as conn:
                    edinet_df = conn.execute(edinet_query, [symbol]).df()

                if not edinet_df.empty:
                    # Supplement the records list, avoiding duplicates
                    existing_keys = {(r.target_label, r.period_date) for r in records}
                    fallback_name = "Unknown (EDINET)"
                    company_name = locals().get("company_name", fallback_name)

                    standard_labels = settings.JQUANTS_V2_LABELS
                    for _, row in edinet_df.iterrows():
                        for label in standard_labels:
                            if label in row and row[label] is not None and str(row[label]) != "":
                                key = (label, str(row["DisclosedDate"]))
                                if key not in existing_keys:
                                    try:
                                        val = float(row[label])
                                        records.append(
                                            FinancialRecord(
                                                market="JP",
                                                symbol=symbol,
                                                company_name=company_name,
                                                target_label=label,
                                                value=val,
                                                unit="JPY",
                                                period_date=str(row["DisclosedDate"]),
                                                fiscal_year=(
                                                    int(row["FiscalYear"])
                                                    if row["FiscalYear"]
                                                    else None
                                                ),
                                                reasoning=f"AI Mapped EDINET -> {label}",
                                            )
                                        )
                                    except (ValueError, TypeError):
                                        continue
            except Exception as e:
                logger.warning(f"Fallback to EDINET failed for {symbol}: {e}")

        else:
            # 3. US Market (Long Format - SEC Native)
            query = """
                SELECT f.tag, f.value, f.unit, CAST(f.end_date AS VARCHAR) as period_date,
                       f.fiscal_year, t.name
                FROM company_facts f
                JOIN tickers t ON f.cik = t.cik
                WHERE t.ticker = ?
            """
            with db.get_us_conn() as conn:
                facts = conn.execute(query, [symbol]).fetchall()

            if facts:
                company_name = next((f[5] for f in facts if f[5] is not None), "Unknown Company")
                # Fetch mappings from audit DB
                with db.get_audit_conn() as conn:
                    mapping_res = conn.execute(
                        "SELECT source_tag, mapped_label, reasoning FROM mapping_audit "
                        "WHERE source_tag LIKE 'US:%'"
                    ).fetchall()
                    mappings = {r[0]: (r[1], r[2]) for r in mapping_res}

                for f in facts:
                    source_tag = f"US:{f[0]}"
                    mapping = mappings.get(source_tag)
                    if mapping and mapping[0] != "Other":
                        records.append(
                            FinancialRecord(
                                market="US",
                                symbol=symbol,
                                company_name=company_name,
                                target_label=mapping[0],
                                value=f[1],
                                unit=f[2],
                                period_date=f[3],
                                fiscal_year=f[4],
                                reasoning=mapping[1],
                            )
                        )
    except Exception as e:
        logger.error(f"Database error for symbol {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {e}") from e

    if not records:
        raise HTTPException(status_code=404, detail=f"No financials found for symbol {symbol}")

    # Sort and paginate
    records.sort(key=lambda x: x.period_date, reverse=True)
    return records[offset : offset + limit]


def manual_sync_task(service: BatchSyncService, market: str):
    """Run incremental sync in the background based on manual trigger."""
    try:
        logger.info(f"Manual trigger: Starting background sync for market: {market}...")
        if market in ["all", "US", "us"]:
            service.sync_market_full("US", incremental=True)
        if market in ["all", "JP", "jp"]:
            service.sync_market_full("JP", incremental=True)
            # Trigger EDINET Sync as part of JP market sync
            try:
                edinet_worker = EDINETSyncWorker()
                edinet_worker.run_incremental_sync()
            except Exception as e:
                logger.error(f"EDINET Sync failed: {e}")

        logger.info(f"Manual trigger: Background sync for {market} completed.")
    except Exception as e:
        logger.error(f"Manual trigger: Background sync failed: {e}")


@app.post("/sync", tags=["Market Data"])
async def trigger_full_sync(
    market: str = Query("all", pattern="^(US|JP|all|us|jp)$"),
):
    """
    Trigger a full or market-wide incremental synchronization in the background.
    """
    # Start the sync task in a separate thread to avoid blocking the API
    threading.Thread(target=manual_sync_task, args=(sync_service, market), daemon=True).start()

    return {
        "status": "accepted",
        "market": market,
        "message": f"Full sync for {market} market(s) started in the background.",
    }


@app.post("/sync/{symbol}", tags=["Market Data"])
async def sync_ticker(symbol: str):
    """
    Manually trigger a financial data sync for a specific ticker.
    This will fetch latest filings and queue them for AI mapping and DB ingestion.
    """
    symbol = symbol.upper()
    jp_ticker_len = 4
    is_jp = symbol.isdigit() and len(symbol) == jp_ticker_len
    market = "JP" if is_jp else "US"
    session_id = f"api-sync-{int(time.time())}"

    try:
        if is_jp:
            logger.info(f"API Triggered JP sync for {symbol}")
            df = sync_service.jp_engine.fetch_statements(symbol)
            if df is not None and not df.empty:
                sync_service.db_queue.put(("JP_INGEST", symbol, df, session_id))
            else:
                return {
                    "status": "skipped",
                    "symbol": symbol,
                    "message": "No data found for JP symbol",
                }
        else:
            logger.info(f"API Triggered US sync for {symbol}")
            data = sync_service.us_engine.fetch_company_facts(symbol)
            if data:
                sync_service.db_queue.put(("US_INGEST", symbol, data, session_id))
            else:
                return {
                    "status": "skipped",
                    "symbol": symbol,
                    "message": "No data found for US symbol",
                }

        return {
            "status": "accepted",
            "symbol": symbol,
            "market": market,
            "session_id": session_id,
            "message": "Sync task queued for background processing.",
        }
    except Exception as e:
        logger.error(f"Manual API sync failed for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=settings.API_PORT)
