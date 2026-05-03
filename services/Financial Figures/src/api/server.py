import os
import random
import threading
import time
from contextlib import asynccontextmanager, contextmanager

import duckdb
from fastapi import FastAPI, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from src.core.config import settings
from src.edinet.sync_worker import EDINETSyncWorker
from src.services.market_sync import BatchSyncService


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

# ... (CORS middleware remains the same)


class DBManager:
    def __init__(self):
        settings.DB_PATH_US.parent.mkdir(parents=True, exist_ok=True)
        settings.DB_PATH_JP.parent.mkdir(parents=True, exist_ok=True)
        settings.DB_PATH_TRACEABILITY.parent.mkdir(parents=True, exist_ok=True)
        self.read_only = os.getenv("DB_READ_ONLY", "false").lower() == "true"
        if self.read_only:
            logger.info("Operating in READ_ONLY mode (Short-lived connections).")

    @contextmanager
    def _get_conn_with_retry(self, db_path: str):
        max_retries = 5
        base_delay = 0.5
        last_exception = None

        for i in range(max_retries):
            try:
                conn = duckdb.connect(db_path, read_only=self.read_only)
                try:
                    yield conn
                finally:
                    conn.close()
                return
            except Exception as e:
                last_exception = e
                # Check if it's a lock error
                if "Locked" in str(e) or "access" in str(e).lower():
                    delay = (base_delay * (2**i)) + (random.random() * 0.1)
                    logger.warning(
                        f"Database busy, retrying in {delay:.2f}s... "
                        f"(Attempt {i + 1}/{max_retries})"
                    )
                    time.sleep(delay)
                    continue
                raise e

        logger.error(
            f"Failed to connect to database after {max_retries} attempts: {last_exception}"
        )
        raise HTTPException(
            status_code=503, detail="Database is temporarily busy. Please try again."
        )

    @contextmanager
    def get_us_conn(self):
        with self._get_conn_with_retry(str(settings.DB_PATH_US)) as conn:
            yield conn

    @contextmanager
    def get_jp_conn(self):
        with self._get_conn_with_retry(str(settings.DB_PATH_JP)) as conn:
            yield conn

    @contextmanager
    def get_audit_conn(self):
        with self._get_conn_with_retry(str(settings.DB_PATH_TRACEABILITY)) as conn:
            yield conn

    @contextmanager
    def get_edinet_conn(self):
        with self._get_conn_with_retry(str(settings.DB_PATH_EDINET)) as conn:
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

    # Fetch facts and ticker info
    try:
        if is_jp:
            query = """
                SELECT f.tag, f.value, f.unit, CAST(f.disclosed_date AS VARCHAR) as period_date,
                       f.fiscal_year, t.name
                FROM company_facts f
                JOIN tickers t ON f.code = t.code
                WHERE f.code = ?
            """
            with db.get_jp_conn() as conn:
                facts = conn.execute(query, [symbol]).fetchall()

            # FALLBACK: Try EDINET DB for additional history/tags
            try:
                # We use 'label' from EDINET as it contains the AI-standardized tag name
                edinet_query = """
                    SELECT label as tag, value, unit,
                           CAST(COALESCE(disclosed_date, ingested_at) AS VARCHAR) as period_date,
                           fiscal_year
                    FROM company_facts
                    WHERE code = ?
                """
                with db.get_edinet_conn() as conn:
                    edinet_facts = conn.execute(edinet_query, [symbol]).fetchall()

                if edinet_facts:
                    # Map EDINET standardized labels to J-Quants shorthand tags if necessary
                    # to match the existing mapping_audit table entries.
                    tag_map = {
                        "NetSales": "Sales",
                        "OperatingProfit": "OP",
                        "OrdinaryProfit": "OdP",
                        "Profit": "NP",
                        "Equity": "Eq",
                        "TotalAssets": "TA",
                        "EquityToAssetRatio": "EqAR",
                    }

                    # Supplement the facts list
                    existing_keys = {(f[0], f[3]) for f in facts}  # (tag, period_date)
                    for ef in edinet_facts:
                        raw_tag = ef[0]
                        normalized_tag = tag_map.get(raw_tag, raw_tag)

                        key = (normalized_tag, ef[3])
                        if key not in existing_keys:
                            # Append with normalized tag and placeholder for name
                            facts.append((normalized_tag, *ef[1:], None))
            except Exception as e:
                logger.warning(f"Fallback to EDINET failed for {symbol}: {e}")
        else:
            query = """
                SELECT f.tag, f.value, f.unit, CAST(f.end_date AS VARCHAR) as period_date,
                       f.fiscal_year, t.name
                FROM company_facts f
                JOIN tickers t ON f.cik = t.cik
                WHERE t.ticker = ?
            """
            with db.get_us_conn() as conn:
                facts = conn.execute(query, [symbol]).fetchall()
    except Exception as e:
        raise HTTPException(
            status_code=404, detail=f"Database error or symbol not found: {e}"
        ) from e

    if not facts:
        raise HTTPException(status_code=404, detail=f"No financials found for symbol {symbol}")

    # Extract company name from the first record that has it
    company_name = next((f[5] for f in facts if f[5] is not None), "Unknown Company")

    # Fetch mappings
    try:
        with db.get_audit_conn() as conn:
            mapping_res = conn.execute(
                "SELECT source_tag, mapped_label, reasoning FROM mapping_audit"
            ).fetchall()
            mappings = {r[0]: (r[1], r[2]) for r in mapping_res}
    except Exception as e:
        logger.error(f"Error fetching mappings from audit DB: {e}")
        mappings = {}

    records = []
    for f in facts:
        source_tag = f"{market}:{f[0]}"
        mapping = mappings.get(source_tag)
        if mapping and mapping[0] != "Other":
            records.append(
                FinancialRecord(
                    market=market,
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
