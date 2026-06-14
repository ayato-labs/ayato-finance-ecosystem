# ADR-0001: Limit Ingestion to Specified Financial Reports

- **Date**: 2026-06-02
- **Status**: Accepted
- **Deciders**: ayato-labs, Antigravity

## Context
Japanese market financial data ingestion via EDINET API v2 currently processes all documents submitted to EDINET. However, the majority of documents (approximately 70-80%) are non-financial or administrative reports (such as extraordinary reports, treasury stock purchase reports, large shareholding reports). 

Attempting to download and parse these documents leads to:
1. High volume of API requests.
2. Frequent `404 Not Found` errors when attempting to extract narrative text from documents that do not contain report text.
3. Excessive triggers of the EDINET API's strict rate limits (`429 Too Many Requests`), which enforces a 60-second global backoff, severely slowing down historical backfilling.
4. Redundant database writes and bloated storage.

To run multi-year backtests efficiently, we only need core financial statements and their corresponding text reports (narratives) from key periodic reports.

## Decision
We will restrict the EDINET data ingestion pipeline (both raw metadata registry and document parsing) to the following 6 form codes:
1. `030000`: Securities Report (有価証券報告書)
2. `030001`: Amendment to Securities Report (有価証券報告書の訂正報告書)
3. `043000`: Quarterly Report (四半期報告書)
4. `043001`: Amendment to Quarterly Report (四半期報告書の訂正報告書)
5. `040000`: Semi-annual Report (半期報告書)
6. `040001`: Amendment to Semi-annual Report (半期報告書の訂正報告書)

Any other document form codes will be discarded during the metadata filtering phase before any download or parse API request is sent.

## Consequences
### Positive
- API request volume for document downloads and parsing will be reduced by 70% to 80%.
- Rate limit (`429`) occurrences will be drastically reduced, allowing much faster backfills.
- Database size and indexing overhead in DuckDB will be optimized.
- Backtests will run faster with a cleaner dataset containing only periodic reports.

### Negative / Risks
- Other reports (e.g. extraordinary reports, earnings releases/短信 via other channels, large shareholding reports) will not be stored in the local database. If we need these in the future, we will have to adjust the filter.

## References
- Issue: N/A
