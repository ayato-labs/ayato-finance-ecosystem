# ADR-0001: Centralized Data Storage and Documentation

- **Date**: 2026-06-14
- **Status**: Accepted
- **Deciders**: Gemini CLI, ayato-labs

## Context
Currently, each data provider service in the `services/` directory stores its database files (mostly DuckDB or SQLite) within its own local `data/` subdirectory. This decentralized approach leads to several issues:
1. **Management Overhead**: Backups and maintenance are difficult as data is scattered across the workspace.
2. **Tight Coupling**: Service logic is physically tied to its local directory structure.
3. **Analysis Bottleneck**: DuckDB's powerful `ATTACH` feature, which allows querying across multiple database files, is harder to use because paths are not standardized.
4. **Documentation Gaps**: Database schemas and API sources are not consistently documented alongside the data.

## Decision
We will centralize all service-specific data into a root-level `data/` directory, organized by source name.
1. **Physical Centralization**: All `.db` and `.duckdb` files will move to `finance/data/<source_name>/`.
2. **Logical Documentation**: Each source folder will contain a `database_design.md` file describing its schema and source API.
3. **Source of Truth**: A `data/master/` folder will be established for common registry and symbol mapping databases.
4. **Exit Strategy**: This structure serves as a bridge to a future migration to a centralized RDBMS (e.g., PostgreSQL/Supabase) when cloud deployment or higher concurrency is required.

## Consequences
### Positive
- **Standardization**: All services follow the same data access pattern.
- **Cross-Source Analysis**: Analysts can easily `ATTACH` multiple databases from a single base path.
- **Improved Maintainability**: Backups and data audits can be performed at the root `data/` level.
- **Integrated Documentation**: Schema definitions live next to the data they describe.

### Negative / Risks
- **File Locking**: DuckDB's single-process write lock remains a constraint (same as before).
- **Migration Effort**: Requires updating path resolution logic in all existing services.

## References
- Plan: `data-centralization-plan.md`
- Issue: Centralizing data storage for better decoupling and analysis.
