# ADR-0005: Direct Database Access for Local Portfolio Analytics

- **Date**: 2026-07-08
- **Status**: Accepted
- **Deciders**: ayato-labs, Antigravity

## Context
In our local-first financial data ecosystem, we initially designed a microservices architecture where each data provider (stock prices, financials, macro indices) exposes a REST API, and the portfolio management application queries these APIs to calculate portfolio statistics (Sharpe ratio, shadow benchmark performance, drawdowns). 

However, running multiple API servers locally and making recurrent HTTP requests across ports introduces unnecessary complexity:
1. **Serialization/Deserialization Overhead**: High-frequency or bulk queries (e.g. 252 days of historical prices for risk calculations) require serializing and deserializing JSON payloads over HTTP.
2. **Operational Overhead**: The user has to maintain 8-9 running API processes just to read data.
3. **Database Attaching Power**: DuckDB supports native database attaching (`ATTACH 'path/to/db' AS db_name`), which allows zero-latency cross-database SQL querying directly on the file system.

## Decision
We will change the primary data access pattern for local portfolio analysis:
1. **Direct DB Reads**: The Asset Management Backend (and any local analysis tools) will read the raw DuckDB database files (`us.duckdb`, `jp.duckdb`, etc.) directly from `FINANCE_DATA_ROOT` using DuckDB's `ATTACH` feature.
2. **API Role Demotion**: Local REST APIs for data providers will only be used for ingestion triggers, external web hooks, or sync operations. They are not to be used as the primary read channel for local analytical queries.
3. **Decoupled Repositories**: Although the folder structure is physically separated, services will maintain logical data structures (schemas) documented in `database_design.md`. The client applications read these files directly from the shared data directory.

## System Diagram
```text
[Asset Management App]
        |
        | (Direct File Access & DuckDB ATTACH)
        v
[FINANCE_DATA_ROOT] 
├── assets.duckdb (User's Portfolio & Transactions)
├── daily_stock_price/jp.duckdb (Historical Stock Prices)
├── daily_stock_price/us.duckdb
└── edinet/edinet.duckdb (Statutory Financials)
```

## Consequences
### Positive
- **Extreme Performance**: Eliminates HTTP roundtrips. Joining transaction data with millions of daily price rows takes milliseconds.
- **Simpler Runtime**: The user only needs to run the Asset Management App to view their portfolio, without starting all data provider servers.
- **Standard SQL Power**: Complex analytics can be written as native multi-database SQL queries.

### Negative / Risks
- **File Lock Constraints**: DuckDB allows multiple concurrent read processes, but only a single write process. Write operations (e.g. daily ingestion running in the background) must yield or coordinate with the analytical read processes.
- **Schema Coupling**: The schema of the underlying DuckDB files becomes a public contract. Any changes to database tables in the ingestion projects must be backward-compatible or coordinated.

## References
- ADR-0001: Centralized Data Storage and Documentation
- ADR-0004: Repository Decentralization Strategy
