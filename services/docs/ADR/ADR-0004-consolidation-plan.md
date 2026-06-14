# ADR-0004: Consolidation of Legacy Financial Services into Specialized Providers

- **Date**: 2026-05-26
- **Status**: Proposed
- **Deciders**: Gemini CLI

## Context
The workspace currently contains redundant projects: `Financial Figures` and `Financial Narratives` (Legacy), which overlap significantly with the newer, more specialized `edinet_provider`, `edgar_provider`, and `jquants_provider`. This redundancy increases maintenance overhead and leads to inconsistent data schemas.

## Decision
Deprecate the legacy projects and consolidate all logic into three specialized "Providers":
1.  **`edinet_provider`**: Single Source of Truth for Japanese statutory filings (EDINET XBRL), qualitative narratives (JP), and the primary Japanese financial database.
2.  **`edgar_provider`**: Single Source of Truth for US statutory filings (SEC EDGAR), qualitative narratives (US), and the primary US financial database.
3.  **`jquants_provider`**: Specialized provider for J-Quants API interaction, used for backfilling historical market data and supplemental metrics.

### Migration Path:
- Move the high-speed SEC Daily Index discovery and parsing logic from `Financial Narratives` to `edgar_provider`.
- Re-align the Japanese market data flow so that `edinet_provider` consumes data from both XBRL and `jquants_provider` where necessary.
- Update `sync_all_dbs.bat` to target only the specialized providers.
- Delete `Financial Figures` and `Financial Narratives` once migration is verified.

## Consequences
### Positive
- **Reduced Complexity**: Clearer responsibility for each project.
- **Data Consistency**: Single schemas for US and JP data.
- **Improved Performance**: All discovery will use the high-speed index-based logic.
### Negative / Risks
- Short-term disruption during the move of code and reconfiguration of the master sync script.

## References
- Target Providers: `edinet_provider`, `edgar_provider`, `jquants_provider`.
- Legacy Projects: `Financial Figures`, `Financial Narratives`.
