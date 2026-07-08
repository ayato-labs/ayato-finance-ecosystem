# ADR-0013: Database Rules and Schema Management

- **Date**: 2026-07-09
- **Status**: Accepted
- **Deciders**: ayato-labs, Antigravity

## Context
With multiple domain-specific DuckDB databases (e.g., `yfinance.duckdb` ~5.8GB, `edinet_narratives.duckdb` ~16.6GB) directly attached by downstream analytics applications, the database schemas act as public APIs. System reliability depends on having structured schema documentation and preventing schema drift. 

To address this, we evaluated introducing a Single Source of Truth (SSoT) for schemas, an automated schema-migration framework, and a centralized master database for metadata coordination.

## Decision
We will implement a lightweight Schema-as-Code and auto-documentation framework, while explicitly avoiding runtime auto-migrations and centralized metadata databases.

1. **Schema-as-Code via Pydantic**: Define all database tables, columns, constraints, and descriptions in Python code using Pydantic models inside each provider service.
2. **Auto-Generated DDL & Markdown**: Develop a script in each provider to read the Pydantic models and output:
   - Creation DDL (`schema.sql`)
   - Markdown Documentation (`database_design.md` or similar)
   These files will be automatically generated and placed in the same directory as the database files (e.g., in `data/yfinance/`).
3. **No Automated/Runtime Migration Engine**: We will NOT implement dynamic runtime schema synchronization (e.g. automatically diffing schemas and calling `ALTER TABLE` at startup). This prevents file corruption on large files and recognizes that schema changes often require custom data backfill logic that auto-sync cannot handle.
4. **Master Metadata Database on Hold**: We will NOT build a centralized database for metadata/state management. Each service will continue to manage its own databases independently for now.

## Consequences
### Positive
- **Guaranteed Documentation Consistency**: The database Markdown docs and SQL schemas will always align with the Python codebase.
- **Safer Schema Evolutions**: Avoids risky automated DDL operations on gigabyte-scale DuckDB databases.
- **Simplicity**: No external database migration frameworks (e.g., Alembic, Flyway) are added to the local environment.

### Negative / Risks
- **Manual Backfills**: The developer must manually write migration SQL/Python scripts for any changes that require historical data transformation or column drops.

## References
- [概念的要件定義書.md](file:///c:/Users/saiha/My_Service/programing/finance/docs/%E6%A6%82%E5%BF%B5%E7%9A%84%E8%A6%81%E4%BB%B6%E5%AE%9A%E7%BE%A9%E6%9B%B8.md)
- [expert_opinion_on_database_rules.md](file:///c:/Users/saiha/My_Service/programing/finance/docs/expert_opinion_on_database_rules.md)
- [migration_overengineering_expert_debate.md](file:///c:/Users/saiha/My_Service/programing/finance/docs/migration_overengineering_expert_debate.md)
