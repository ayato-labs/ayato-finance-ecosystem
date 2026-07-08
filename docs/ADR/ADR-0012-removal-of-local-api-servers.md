# ADR-0012: Removal of Local API Servers from Ingestion Providers

- **Date**: 2026-07-09
- **Status**: Accepted
- **Deciders**: ayato-labs, Antigravity

## Context
Following the decision in [ADR-0005: Direct Database Access](file:///c:/Users/saiha/My_Service/programing/finance/docs/ADR/ADR-0005-direct-db-access.md), the client portfolio applications attach DuckDB databases directly via the filesystem rather than making HTTP REST queries to local provider APIs. 

Despite this, several ingestion services (like `yfinance_provider`, `fred_provider`, and `edinet_provider`) still contained FastAPI apps, uvicorn configurations, and server startup CLI parameters. This led to unnecessary dependencies, complex test suites, and potential confusion regarding the communication boundaries of the local ecosystem.

## Decision
We will completely remove all API server definitions, server-launching sub-commands, FastAPI endpoints, and uvicorn dependencies from all provider services. 
1. **CLI Ingestion Only**: Providers will expose only command-line interfaces (CLIs) or direct script executions for ingesting data.
2. **Delete API Modules**: Remove all `src/api` or server folders inside individual provider directories.
3. **Simplify Tests**: Remove all FastAPI `TestClient` integrations and E2E API tests, keeping only functional database ingestion checks.

## Consequences
### Positive
- **Reduced Overhead**: Zero overhead from running HTTP server processes on the local machine.
- **Smaller Dependencies**: Cleans up unnecessary libraries (FastAPI, uvicorn, testclient) from the service requirements.
- **Clearer Architecture**: Removes any ambiguity about how data is transferred. Filesystem direct attach is the single SSoT query method.

### Negative / Risks
- **No Network Ingestion Trigger**: Ingestion runs can only be triggered via shell command execution/cron jobs rather than HTTP POST endpoints.

## References
- ADR-0005: Direct Database Access for Local Portfolio Analytics
- ADR-0011: One Service Per Unique Information Source
