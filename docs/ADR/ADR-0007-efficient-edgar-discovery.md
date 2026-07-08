# ADR-0003: Efficient EDGAR Incremental Sync via Daily Index

- **Date**: 2026-05-26
- **Status**: Accepted
- **Deciders**: Gemini CLI

## Context
The previous EDGAR sync logic used a brute-force approach, scanning 10,000+ tickers individually. This took ~20 minutes for a single daily check, making workspace-wide updates extremely slow.

## Decision
Switch from ticker-by-ticker scanning to **SEC Daily Index** (`master.idx`) based discovery.
1. Download the daily index for the target date.
2. Filter for `10-K` and `10-Q` forms across all companies.
3. Resolve specific metadata and primary document names only for discovered new filings.
4. Download specific HTML documents (`.htm`) instead of full submission texts (`.txt`) to avoid recursion depth issues during parsing.

## Consequences
### Positive
- Discovery time reduced from ~20 minutes to <10 seconds.
- Significantly lower load on SEC servers.
- Resolved `RecursionError` in parsing by targeting smaller HTML documents.
### Negative / Risks
- Dependency on the SEC index availability (mitigated by handling 403/404 for weekends/holidays).

## References
- Service: `Financial Narratives`
- Files: `src/edgar_fetcher.py`, `src/batch_fetch.py`
