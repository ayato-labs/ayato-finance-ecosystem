# ADR-0004: Transition to Clean Monorepo and Ephemeral Raw Data Policy

- **Date**: 2026-06-15
- **Status**: Proposed
- **Deciders**: Gemini CLI, ayato-labs

## Context
The current codebase has outgrown its initial flat structure. While `apps/` and `libs/` directories exist, the core logic remains concentrated in the root `src/` directory, leading to package naming ambiguity (e.g., `import src.storage`). Furthermore, strict storage constraints on the local environment necessitate a policy where large raw files (HTML/XBRL) are not persisted on disk.

## Decision
We will reorganize the project into a formal monorepo and enforce an in-memory-only processing policy for raw data.

1.  **Monorepo Structure**:
    - `libs/core/`: Common infrastructure (Logging, Database Schema, Shared Models).
    - `apps/provider/`: The data ingestion engine (Fetcher, Parser, Sync Logic).
    - `apps/api/`: Data serving layer (FastAPI/REST).
2.  **Absolute Namespace Adoption**:
    - Abandon `src.*` imports.
    - Use `edgar_core.*` and `edgar_provider.*` as defined in `pyproject.toml` or via editable installs.
3.  **Ephemeral Raw Data Policy**:
    - The `EdgarFetcher` shall return raw data as strings or byte streams.
    - The `EdgarParser` and `EdgarQuantitative` shall process these streams directly in memory.
    - No raw `.html`, `.xml`, or `.xbrl` files shall be saved to the local filesystem during the standard sync process.
4.  **Verification Strategy**:
    - Implement unit tests for each new library/app location.
    - Use `pytest` to ensure refactored imports are functional.

## Consequences
### Positive
- **Maintainability**: Clear separation of concerns between infrastructure and domain logic.
- **Scalability**: New data sources or apps can be added by following the same pattern.
- **Resource Efficiency**: Significant reduction in disk I/O and storage requirements.

### Negative / Risks
- **Memory Pressure**: High memory usage when processing very large 10-K filings. This must be mitigated with stream processing or explicit garbage collection.
- **Debug Difficulty**: Without local raw files, troubleshooting parser failures requires re-fetching from the SEC API, which is subject to rate limits.

## References
- ADR-0001: Centralized Data Storage and Documentation
- ADR-0003: Smart Repair and Data Completeness for EDGAR
