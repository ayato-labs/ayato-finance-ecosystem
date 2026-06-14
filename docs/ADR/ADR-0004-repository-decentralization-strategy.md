# ADR-0004: Repository Decentralization Strategy (Monorepo to Polyrepo)

- **Date**: 2026-06-15
- **Status**: Proposed / Long-term Vision
- **Deciders**: Gemini CLI, ayato-labs

## Context
Currently, the entire "finance" ecosystem (data providers, analysis apps, core utilities, and infrastructure scripts) is managed within a single Git repository (Monorepo). As the system grows, we face several emerging challenges:
1. **Coupled History**: Commit logs for unrelated services (e.g., Crypto and EDINET) are mixed.
2. **Release Complexity**: A minor change in one provider triggers CI/CD or metadata updates for the entire project.
3. **Dependency Hell**: Managing a single `.venv` or cross-service dependencies becomes increasingly fragile.
4. **Maintenance Burden**: The repository size makes it harder for new contributors or sub-agents to focus on specific domains.

## Decision
We aim for a "Polyrepo" (Multi-repo) architecture where each system is a self-contained unit. The transformation will follow these strategic pillars:

### 1. The "finance-core" Extraction
- **Action**: Extract shared logic (DuckDB connection managers, standardized logging, common data contracts) into a private Python package named `finance-core`.
- **Reason**: To avoid code duplication while maintaining physical separation between repositories.

### 2. Service-Level Decentralization
- **Action**: Split the `services/` directory into independent repositories:
  - `finance-jquants-provider`
  - `finance-edinet-provider`
  - `finance-edgar-provider`
  - `finance-market-common` (Forex, Index, Macro)
- **Reason**: To allow each service to have its own lifecycle, versioning, and deployment stack.

### 3. Absolute Path Abstraction (Environment Variables)
- **Action**: Fully replace relative pathing (e.g., `../../data`) with standardized environment variables:
  - `FINANCE_DATA_ROOT`: Base path for the centralized `data/` directory.
  - `FINANCE_LOG_ROOT`: Base path for unified logging.
- **Reason**: To ensure services can find the centralized data storage regardless of where their repository is cloned on the system.

### 4. Orchestration Repo
- **Action**: Maintain a "Master" repository or a central "Workspace" repo that uses `git submodules` or a simple orchestration script (like the current `.bat` files) to coordinate cross-repository tasks.

## Ideal State Architecture
```text
Root/
├── finance-core (Repo: Shared Utils)
├── finance-edinet-provider (Repo)
├── finance-jquants-provider (Repo)
├── finance-asset-management-app (Repo: UI)
└── finance-data (Centralized storage, managed independently)
```

## Consequences
### Positive
- **Domain Isolation**: Developers can work on a single service without context-switching or fearing side effects.
- **Optimized CI/CD**: Faster test execution and focused deployment pipelines.
- **Granular Permissions**: Repository-level access control.

### Negative / Risks
- **Overhead**: Managing multiple repositories requires more sophisticated version management (SemVer) for the core library.
- **Local Setup**: Developers need to clone multiple repositories to run the full ecosystem locally.

## Prerequisite Tasks
1. Standardize all `services/**/config.py` to use `FINANCE_DATA_ROOT`.
2. Refactor shared `DuckDBManager` and `logging_config` into a single `libs/` folder before full extraction.
3. Establish a standard `README.md` and `pyproject.toml` template for all future split repositories.

## References
- ADR-0001: Centralized Data Storage and Documentation
- ADR-0002: Automated High-Water Mark Synchronization
