# ADR-0005: Data Integrity Guard and Data Chaos Testing

- **Date**: 2026-06-15
- **Status**: Accepted
- **Deciders**: Gemini CLI, ayato-labs

## Context
As defined in ADR-0004, the system does not persist raw HTML/XBRL files to save storage. This means any parsing error or data corruption during fetching leads to permanent data loss if not detected immediately. We need a way to ensure that only "valid" data enters the DuckDB storage and that the pipeline can recover from transient data corruption.

## Decision
We will implement an "Integrity Guard" at the storage layer and a "Data Chaos" framework for verification.

1.  **Integrity Guard (Basic Validation)**:
    - `EdgarStorage.save_filing` shall validate that mandatory keys exist in metadata and that qualitative sections are not empty.
    - `EdgarStorage.save_facts` shall validate that the incoming DataFrame contains at least one record.
    - Invalid data shall be rejected (not saved), raising a `ValueError` or a custom exception to trigger a "repair" on the next sync run.

2.  **Data Chaos Testing**:
    - We will implement chaos tests that deliberately provide truncated HTML/XBRL content to the parser/storage.
    - These tests will verify that the Integrity Guard correctly rejects corrupted data.

3.  **Self-Healing Loop**:
    - By combining rejection at the storage level with the existing Smart Repair logic, we create a natural self-healing loop.

## Consequences
### Positive
- **Data Quality**: Prevents the database from being polluted with "empty" or "broken" filings.
- **Resilience**: The system detects and eventually repairs data that was corrupted during transit.

### Negative / Risks
- **False Rejections**: Overly strict validation might reject valid but unusual filings.

## References
- ADR-0003: Smart Repair and Data Completeness for EDGAR
- ADR-0004: Transition to Clean Monorepo and Ephemeral Raw Data Policy
