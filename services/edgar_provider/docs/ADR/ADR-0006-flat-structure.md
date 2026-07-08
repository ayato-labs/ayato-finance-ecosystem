# ADR-0006: Revert to Flat src/ Structure for CLI Tool

- **Date**: 2026-07-08
- **Status**: Accepted
- **Deciders**: opencode, ayato-labs

## Context
ADR-0004 proposed a monorepo structure with `apps/` and `libs/` directories to support multiple applications (CLI, API server, etc.). However, `edgar_provider` is a single-purpose CLI tool that generates DuckDB databases. The monorepo structure introduced unnecessary complexity:

- Dual `src/` directories caused confusion (old `src/` vs `apps/*/src/`)
- Import paths required package installation (`edgar_core.*`, `edgar_provider.*`)
- Directory traversal for data path resolution became fragile (`parents[6]`)
- No actual benefit since only one CLI entry point exists

## Decision
We will revert to a flat `src/` structure and consolidate all code into a single package directory.

1. **Flat Structure**:
   ```
    edgar_provider/
    ├── src/
    │   ├── __init__.py
    │   ├── fetcher.py
    │   ├── parser.py
    │   ├── storage.py
    │   ├── quantitative.py
    │   ├── pipeline.py
    │   └── logging.py
    ├── main.py
    └── pyproject.toml
   ```

2. **Import Convention**: Use relative imports within `src.*` or absolute `src.*` imports.

3. **Package Distribution**: `pyproject.toml` will reference only `src/` as the package root.

4. **Data Storage**: All data files (DuckDB) will be stored under `finance/data/` (monorepo root), not within the service directory.

## Consequences
### Positive
- **Simplicity**: Single import path, no package installation required for development.
- **Maintainability**: All code in one location, easy to navigate.
- **Correct Path Resolution**: Data paths resolve to `finance/data/` without fragile parent traversal.

### Negative / Risks
- **No API Server**: If a REST API is needed later, it must be added as a separate service or within the same `src/` structure.

## References
- ADR-0004: Transition to Clean Monorepo (Superseded by this ADR)
- ADR-0003: Smart Repair and Data Completeness
- ADR-0005: Data Integrity Guard
