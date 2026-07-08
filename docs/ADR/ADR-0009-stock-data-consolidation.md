# ADR-0005: Consolidation of Stock Price Ingestion into yfinance_provider

- **Date**: 2026-05-26
- **Status**: Accepted
- **Deciders**: Gemini CLI

## Context
The workspace contained two overlapping services for stock price data: `daily_stock_price` (Legacy) and `yfinance_provider` (New). The legacy project had superior market discovery (JPX/Nasdaq scrapers) and validation logic, while the new project had a better DuckDB schema and asynchronous engine.

## Decision
Decommission `daily_stock_price` and consolidate all stock data logic into `yfinance_provider`.
1.  **Migration**: Ported `UniverseManager` (market discovery) and `DataValidator` (OHLC logic checks) from the legacy project to `yfinance_provider`.
2.  **Integration**: Updated `SyncEngine` in `yfinance_provider` to perform data validation before ingestion.
3.  **CLI Enhancement**: Added `--sync-market` flag to `yfinance_provider/main.py` to allow market-wide synchronization.
4.  **Consolidation**: Updated `sync_all_dbs.bat` to call `yfinance_provider` directly for all market price data.

## Consequences
### Positive
- **Unified Logic**: One service now handles all stock price and basic financial metric ingestion via yfinance.
- **Improved Quality**: The new provider now benefits from the rigorous validation logic of the legacy project.
- **Automation**: Full market discovery is now integrated into the modern provider.
### Negative / Risks
- Dependency on scraping external sites (JPX/Nasdaq) for ticker lists, which can be fragile.

## References
- Target Provider: `yfinance_provider`
- Retired Project: `daily_stock_price`
