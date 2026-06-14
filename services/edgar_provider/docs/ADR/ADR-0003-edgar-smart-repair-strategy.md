# ADR-0003: Smart Repair and Data Completeness for EDGAR

- **Date**: 2026-06-15
- **Status**: Accepted
- **Deciders**: Gemini CLI, ayato-labs

## Context
Following the integration of `edgartools` (ADR-0002), the `edgar_provider` now has the capability to extract quantitative financial facts. However, the existing database contains many records ingested using the legacy logic, which only captured qualitative text sections. 

The initial "skip if exists" logic in the synchronization process would result in these historical records never being enriched with financial data, leading to a permanent gap in quantitative analysis capabilities.

## Decision
We will implement a "Smart Repair" strategy instead of a full database reset.

1.  **Completeness-Aware Discovery**: The synchronization logic will be updated to check not just for the *existence* of a filing, but for its *completeness* (i.e., whether it has associated records in the `company_facts` table).
2.  **In-Place Enrichment**: If a filing exists in the `filings` table but lacks entries in `company_facts`, the system will trigger the quantitative extraction process for that record without re-downloading or re-parsing the qualitative sections.
3.  **Dedicated Repair CLI**: A new `repair-facts` command will be added to `main.py` to allow a one-time bulk update of all historical records.
4.  **Resource Preservation**: This approach avoids unnecessary SEC API calls and preserves existing qualitative data and its metadata.

## Consequences
### Positive
- **Data Integrity**: Ensures that all records in the database eventually reach the same level of detail (Qualitative + Quantitative).
- **Efficiency**: Only performs the missing extraction steps, saving bandwidth and compute time.
- **SEC Compliance**: Minimizes the number of requests to the SEC servers by reusing already downloaded information (if available) or precisely targeting missing data.

### Negative / Risks
- **Logic Complexity**: The "skip" logic becomes slightly more complex as it now involves a cross-table check.
- **Processing Time**: The first bulk repair for a large database may take significant time due to the volume of XBRL data to be processed.

## References
- ADR-0001: Centralized Data Storage and Documentation
- ADR-0002: Automated High-Water Mark Synchronization
- Implementation: `services/edgar_provider/src/storage.py`, `services/edgar_provider/main.py`
