from __future__ import annotations

import asyncio
import math
import sys
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from core.aggregator import ExternalApiAggregator
from core.calculator import BenchmarkCalculator
from core.config import settings
from core.database import DatabaseManager
from core.models import (
    AssetSummary,
    AssetType,
    BenchmarkSummary,
    PortfolioSummary,
    Transaction,
    TransactionType,
)

# Configure loguru
logger.remove()
logger.add(sys.stderr, level=settings.log_level)
logger.add("logs/backend_error.log", level="ERROR", rotation="10 MB")
logger.add("logs/backend.log", level=settings.log_level, rotation="10 MB")


app = FastAPI(title="Ayato Asset API")


# Custom handler to log validation errors (422)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    body = await request.body()
    logger.error(f"Validation Error: {exc}")
    logger.error(f"Request Body: {body.decode()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": body.decode()},
    )


# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

db = DatabaseManager(db_path=settings.db_path)
aggregator = ExternalApiAggregator(
    price_api_url=settings.price_api_url,
    financials_api_url=settings.financials_api_url,
    index_api_url=settings.index_api_url,
    macro_api_url=settings.macro_api_url,
    forex_api_url=settings.forex_api_url,
    crypto_api_url=settings.crypto_api_url,
)


@app.get("/")
async def root():
    return {"status": "ok", "service": "Ayato Asset Management"}


@app.post("/transactions")
async def create_transaction(tx: Transaction):
    try:
        tx_id = db.add_transaction(tx)
        return {"id": tx_id, "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/transactions", response_model=list[Transaction])
async def list_transactions():
    return db.get_all_transactions()


@app.delete("/transactions/{tx_id}")
async def delete_transaction(tx_id: int):
    try:
        success = db.delete_transaction(tx_id)
        if not success:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return {"status": "success", "message": "Transaction deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/transactions/{tx_id}", response_model=Transaction)
async def get_transaction(tx_id: int):
    tx = db.get_transaction(tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


@app.put("/transactions/{tx_id}")
async def update_transaction(tx_id: int, tx: Transaction):
    logger.info(f"PUT /transactions/{tx_id} - Data: {tx}")
    try:
        success = db.update_transaction(tx_id, tx)
        if not success:
            logger.warning(f"Transaction {tx_id} not found for update.")
            raise HTTPException(status_code=404, detail="Transaction not found")
        logger.info(f"Transaction {tx_id} successfully updated.")
        return {"status": "success", "message": "Transaction updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error during update_transaction: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/portfolio", response_model=PortfolioSummary)
async def get_portfolio(currency: str = "JPY"):
    logger.info(f"get_portfolio called with currency: {currency}")
    try:
        positions = db.get_positions()

        # Fetch benchmarks and macro indicators in parallel
        benchmark_tickers = {"S&P 500": "^GSPC", "Nikkei 225": "^N225"}
        benchmark_tasks = {
            name: asyncio.create_task(aggregator.get_benchmark_performance(ticker))
            for name, ticker in benchmark_tickers.items()
        }
        macro_task = asyncio.create_task(aggregator.get_latest_macro_value("DGS10"))
        fed_funds_task = asyncio.create_task(aggregator.get_latest_macro_value("DFF"))

        asset_tasks = [aggregator.enrich_asset_data(pos[0], pos[1]) for pos in positions]
        results = await asyncio.gather(*asset_tasks)

        # Fetch all exchange rates needed (against USD HUB)
        display_currency = currency.upper()
        currencies_needed = list(
            set(
                [pos[4] for pos in positions if len(pos) > 4 and pos[4]]
                + ["USD", display_currency]
            )
        )
        forex_tasks = {
            cur: asyncio.create_task(aggregator.get_latest_exchange_rate(cur))
            for cur in currencies_needed
        }
        forex_rates = {}
        for cur, task in forex_tasks.items():
            # Fallback to 1.0 if task returns None
            forex_rates[cur] = await task or 1.0

        target_rate_to_usd = forex_rates.get(display_currency, 1.0)

        # --- Pre-calculate S&P 500 Shadow Map ---
        sp500_map = {}
        current_sp500_price_usd = 0
        try:
            sp500_history = await aggregator.get_historical_data_raw("^GSPC")
            for entry in sp500_history:
                try:
                    date_str = entry["Date"][:10]
                    # Get values with defaults
                    open_p = entry.get("Open") or 0
                    high_p = entry.get("High") or 0
                    low_p = entry.get("Low") or 0
                    close_p = entry.get("Close") or 0

                    avg_p = (open_p + high_p + low_p + close_p) / 4
                    if avg_p > 0:
                        sp500_map[date_str] = avg_p
                except Exception:
                    continue
            if sp500_history:
                current_sp500_price_usd = sp500_history[-1].get("Close") or 0
        except Exception as e:
            logger.error(f"Error preparing S&P 500 map: {e}")

        transactions = db.get_all_transactions()

        # --- Asset Processing & Market Value Calculation ---
        asset_summaries = []
        total_market_value_usd = 0

        for pos, enriched in zip(positions, results, strict=False):
            ticker, asset_type_str, qty, avg_price_orig = pos[:4]
            currency_orig = pos[4] if len(pos) > 4 else "USD"
            current_price_orig = enriched.get("current_price") or avg_price_orig

            asset_rate_to_usd = forex_rates.get(currency_orig, 1.0)
            current_price_usd = current_price_orig * asset_rate_to_usd

            # For display purposes, convert prices to target currency
            # Target Rate is '1 Unit of Target = X USD'
            # So Target = USD / Target_Rate_to_USD
            display_avg_price = (
                (avg_price_orig * asset_rate_to_usd) / target_rate_to_usd
                if target_rate_to_usd > 0
                else avg_price_orig
            )
            display_current_price = (
                current_price_usd / target_rate_to_usd
                if target_rate_to_usd > 0
                else current_price_usd
            )

            market_value = qty * display_current_price

            # Individual Benchmark for this asset (Geometric)
            a_bench_cost, a_bench_val, _ = BenchmarkCalculator.create_shadow_performance(
                transactions,
                sp500_map,
                current_sp500_price_usd,
                ticker_filter=ticker,
                forex_rates=forex_rates,
            )
            a_bench_gain = ((a_bench_val / a_bench_cost - 1) * 100) if a_bench_cost > 0 else 0

            asset_summaries.append(
                AssetSummary(
                    id=f"{ticker}-{asset_type_str}-{display_currency}",
                    ticker=ticker,
                    asset_type=AssetType(asset_type_str),
                    total_quantity=qty,
                    average_price=display_avg_price,
                    current_price=display_current_price,
                    market_value=market_value,
                    currency=display_currency,
                    benchmark_gain_percent=a_bench_gain,
                    benchmark_unrealized_gain=(
                        (a_bench_val - a_bench_cost) / target_rate_to_usd
                        if target_rate_to_usd > 0
                        else (a_bench_val - a_bench_cost)
                    ),
                    crypto_metadata=enriched.get("crypto_metadata"),
                )
            )
            total_market_value_usd += qty * current_price_usd

        # --- Portfolio Shadow Benchmark & Alpha Calculation ---
        total_bench_cost_usd, total_bench_market_value_usd, _ = (
            BenchmarkCalculator.create_shadow_performance(
                transactions, sp500_map, current_sp500_price_usd, forex_rates=forex_rates
            )
        )

        # Calculate TRUE USD Cost Basis (Historical cost for currently held quantities)
        total_cost_basis_usd = 0
        for asset in asset_summaries:
            asset_txs = [tx for tx in transactions if tx.ticker == asset.ticker]
            buys = [tx for tx in asset_txs if tx.transaction_type == TransactionType.BUY]
            if buys:
                # Correctly convert each transaction to USD based on its recorded currency
                asset_total_spent_usd = sum(
                    tx.quantity * tx.price * forex_rates.get(tx.currency, 1.0) for tx in buys
                )
                asset_total_qty_bought = sum(tx.quantity for tx in buys)
                asset_avg_cost_usd = asset_total_spent_usd / asset_total_qty_bought
                total_cost_basis_usd += asset.total_quantity * asset_avg_cost_usd

        alpha_metrics = BenchmarkCalculator.calculate_alpha_metrics(
            total_market_value_usd,
            total_cost_basis_usd,
            total_bench_market_value_usd,
            total_bench_cost_usd,
        )

        total_unrealized_gain = (
            (total_market_value_usd - total_cost_basis_usd) / target_rate_to_usd
            if target_rate_to_usd > 0
            else (total_market_value_usd - total_cost_basis_usd)
        )
        total_cost_basis = (
            total_cost_basis_usd / target_rate_to_usd
            if target_rate_to_usd > 0
            else total_cost_basis_usd
        )
        total_market_value = (
            total_market_value_usd / target_rate_to_usd
            if target_rate_to_usd > 0
            else total_market_value_usd
        )

        alpha_value = (
            alpha_metrics["alpha_value_usd"] / target_rate_to_usd
            if target_rate_to_usd > 0
            else alpha_metrics["alpha_value_usd"]
        )
        alpha_percent = alpha_metrics["alpha_percent"]
        shadow_gain_percent = alpha_metrics["benchmark_return"]
        shadow_market_value = (
            alpha_metrics["shadow_market_value_usd"] / target_rate_to_usd
            if target_rate_to_usd > 0
            else alpha_metrics["shadow_market_value_usd"]
        )
        shadow_unrealized_gain = (
            (alpha_metrics["shadow_market_value_usd"] - alpha_metrics["shadow_cost_usd"])
            / target_rate_to_usd
            if target_rate_to_usd > 0
            else (alpha_metrics["shadow_market_value_usd"] - alpha_metrics["shadow_cost_usd"])
        )

        # Calculate weights and individual gain percent
        for asset in asset_summaries:
            asset.weight = (
                (asset.market_value / total_market_value * 100) if total_market_value > 0 else 0
            )
            asset.unrealized_gain = asset.market_value - (
                asset.total_quantity * asset.average_price
            )
            cost_total = asset.total_quantity * asset.average_price
            asset.gain_percent = (
                (asset.unrealized_gain / cost_total * 100) if cost_total > 0 else 0
            )

        logger.info(
            f"Alpha calculation complete: Alpha={alpha_percent:.2f}% "
            f"(Real={alpha_metrics['portfolio_return']:.2f}% vs "
            f"Shadow={shadow_gain_percent:.2f}%)"
        )

        # Collect benchmarks (S&P 500 uses shadow gain)
        benchmarks = []
        for name, task in benchmark_tasks.items():
            perf = await task
            if perf is not None:
                final_perf = perf
                if benchmark_tickers[name] == "^GSPC" and shadow_gain_percent != 0:
                    final_perf = shadow_gain_percent

                benchmarks.append(
                    BenchmarkSummary(
                        name=name, ticker=benchmark_tickers[name], gain_percent=final_perf
                    )
                )

        # Prepare data for Risk Calculation
        history_tasks = {
            pos[0]: asyncio.create_task(aggregator.get_historical_data_raw(pos[0]))
            for pos in positions
        }
        sp500_history_task = asyncio.create_task(aggregator.get_historical_data_raw("^GSPC"))

        all_histories = {}
        for ticker, task in history_tasks.items():
            h = await task
            if h:
                all_histories[ticker] = {row["Date"][:10]: row["Close"] for row in h}

        sp500_h = await sp500_history_task
        sp500_history_map = {row["Date"][:10]: row["Close"] for row in sp500_h} if sp500_h else {}

        common_dates = sorted(sp500_history_map.keys())[-252:]
        portfolio_daily_values = []
        benchmark_daily_values = []

        holdings = {pos[0]: pos[2] for pos in positions}
        current_sp500_price_usd = (
            sp500_map.get(datetime.now().strftime("%Y-%m-%d"))
            or list(sp500_map.values())[-1]
            if sp500_map
            else 0
        )
        shadow_units = (
            total_bench_market_value_usd / current_sp500_price_usd
            if current_sp500_price_usd > 0
            else 0
        )

        for date in common_dates:
            p_val = sum(
                all_histories[t][date] * holdings[t]
                for t in holdings
                if t in all_histories and date in all_histories[t]
            )
            if p_val > 0:
                portfolio_daily_values.append(p_val)
                benchmark_daily_values.append(shadow_units * sp500_history_map[date])

        risk_free_rate = await macro_task or 0.0
        fed_funds_rate = await fed_funds_task or 0.0
        from core.calculator import PortfolioCalculator

        # Calculate base metrics and get return series for advanced metrics
        vol, sharpe, max_dd, p_returns = PortfolioCalculator.calculate_risk_metrics(
            portfolio_daily_values, risk_free_rate
        )
        b_vol, b_sharpe, b_max_dd, b_returns = PortfolioCalculator.calculate_risk_metrics(
            benchmark_daily_values, risk_free_rate
        )

        # Calculate advanced cross-metrics
        sortino, beta, correlation = PortfolioCalculator.calculate_advanced_metrics(
            p_returns, b_returns, risk_free_rate
        )

        symbol_map = {"JPY": "¥", "USD": "$", "EUR": "€", "GBP": "£", "AUD": "A$", "CAD": "C$"}
        display_symbol = symbol_map.get(display_currency, display_currency)

        # Prepare the final summary
        summary = PortfolioSummary(
            total_market_value=total_market_value,
            total_unrealized_gain=total_unrealized_gain,
            gain_percent=(
                (total_unrealized_gain / total_cost_basis * 100) if total_cost_basis != 0 else 0
            ),
            display_currency=display_currency,
            display_symbol=display_symbol,
            volatility=vol,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            benchmark_volatility=b_vol,
            benchmark_sharpe=b_sharpe,
            benchmark_max_drawdown=b_max_dd,
            sortino_ratio=sortino,
            beta=beta,
            correlation=correlation,
            assets=asset_summaries,
            benchmarks=benchmarks,
            shadow_market_value=shadow_market_value,
            shadow_gain_percent=shadow_gain_percent,
            shadow_unrealized_gain=shadow_unrealized_gain,
            alpha_value=alpha_value,
            alpha_percent=alpha_percent,
            macro_indicators={
                "10Y Treasury Yield": risk_free_rate,
                "Fed Funds Rate": fed_funds_rate,
            },
        )

        # Convert to dict and clean NaN/inf for JSON compliance
        def clean_json_data(obj: Any) -> Any:
            if isinstance(obj, list):
                return [clean_json_data(i) for i in obj]
            if isinstance(obj, dict):
                return {k: clean_json_data(v) for k, v in obj.items()}
            if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
                return None
            return obj

        # Use model_dump to get dict (Pydantic v2)
        return clean_json_data(summary.model_dump())
    except Exception as e:
        logger.exception(f"Error in get_portfolio: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn

    logger.info(
        f"Starting Asset Management Backend on {settings.backend_host}:{settings.backend_port}..."
    )
    uvicorn.run(app, host=settings.backend_host, port=settings.backend_port)
