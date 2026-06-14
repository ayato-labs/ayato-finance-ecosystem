# ADR-0002: Automated High-Water Mark Synchronization for EDINET and J-Quants

- **Date**: 2026-06-14
- **Status**: Accepted
- **Deciders**: Gemini CLI, ayato-labs

## Context
Initially, the synchronization logic for EDINET and J-Quants used a fixed "lookback window" (e.g., 7 or 30 days) passed via CLI arguments. This approach had a significant risk of "data gaps": if the synchronization script was not executed for a period exceeding the window, filings and statements released during that gap would be permanently missed. 

Furthermore, the J-Quants financial data sync was performed per-ticker, which was prohibitively slow for daily full-market updates.

## Decision
We will transition from "Fixed Window Sync" to "Automated High-Water Mark Sync".

1. **Smart Discovery**: Both EDINET and J-Quants engines will now query their respective databases (`filings` and `company_facts`) to identify the maximum date of already ingested records.
2. **Automatic Gap Bridging**: The sync process will automatically set the start date to the day following the detected high-water mark, ensuring that all data up to the current date is scanned and ingested.
3. **J-Quants Bulk Ingestion**: Implementation of a daily bulk fetching logic (`--sync-daily`) that retrieves all statements released on a specific date in a single API call, replacing the inefficient per-ticker loop.
4. **CLI Simplification**: The `sync_all_finance.bat` script will no longer require hardcoded `--days` parameters for these services, relying instead on the engine's internal state.

## Consequences
### Positive
- **Reliability**: Eliminates human error and data loss caused by skipped execution days.
- **Performance**: J-Quants financial data ingestion is now orders of magnitude faster due to bulk API usage.
- **Maintainability**: Reduced complexity in orchestrating scripts (batch files) as they no longer need to manage sync windows.

### Negative / Risks
- **Initial Sync Load**: If a database is empty or very old, the first sync might take longer as it tries to fill the entire gap (though this is a one-time cost).
- **API Dependency**: Relies on the availability of historical data within the API's own retention period (e.g., EDINET's 5-year limit).

## References
- ADR-0001: Centralized Data Storage and Documentation
- Service Refactoring: `edinet_provider/src/datalake/engine.py`, `jquants_provider/src/engine.py`
