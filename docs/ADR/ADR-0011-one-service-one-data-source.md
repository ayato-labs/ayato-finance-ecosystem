# ADR-0011: One Service Per Unique Information Source (Data Consolidation)

- **Date**: 2026-07-08
- **Status**: Accepted
- **Deciders**: ayato-labs, Antigravity

## Context
Initially, the data ingestion platform was split into various domain-specific services, such as:
- `yfinance_provider` (for stock prices/financials)
- `index` (for stock index prices using yfinance)
- `forex` (for exchange rates using yfinance)
- `daily_crypto_price` (for cryptocurrency prices using yfinance)
- `fred_provider` (placeholder for FRED api)
- `macro` (for economic indicators using FRED api)

This led to duplicate implementations of the same data provider libraries (like `yfinance` and `fredapi`) across multiple local services, complicating configuration management, logging patterns, and database file allocations.

## Decision
We will strictly enforce the architectural principle of **"One Service per Unique Information Source"**:
1. **Source-Based Boundaries**: Service boundaries are mapped directly to their external API provider instead of domain-level output concepts.
2. **yfinance Consolidation**: All logic and data tables related to Yahoo Finance (`prices` for stocks/indices/crypto, `crypto_metadata`, `forex_rates`) are consolidated into a single service: `yfinance_provider`.
3. **FRED Consolidation**: All logic and databases related to the Federal Reserve Economic Data (`fredapi`) are consolidated into a single service: `fred_provider`.
4. **Deletion of Redundant Projects**: Obsolete projects (`index`, `forex`, `daily_crypto_price`, and `macro`) are deleted from the ecosystem.

## Consequences
### Positive
- **Zero Redundancy**: Avoids duplicate client configuration, rate limit handling, and logging setups.
- **Unified Schema Control**: Database files (e.g. `yfinance.duckdb`) hold all datasets fetched from that provider, making joins much simpler.
- **Easier Maintenance**: Standardizes dependencies (e.g. updating the `yfinance` package is done once instead of 4 times).

### Negative / Risks
- **Monolithic Storage**: `yfinance.duckdb` file size grows as it stores diverse types of market data.
- **Loss of Domain Isolation**: Any changes to stock fetching logic could hypothetically disrupt crypto or forex runs if not carefully modularized.

## References
- ADR-0004: Repository Decentralization Strategy
- ADR-0005: Direct Database Access for Local Portfolio Analytics
