# ADR-0002: Standardized Static Analysis with Ruff

- **Date**: 2026-05-26
- **Status**: Accepted
- **Deciders**: Gemini CLI

## Context
Code quality and style varied across services, leading to maintenance friction. A common standard was needed, especially for CI integration.

## Decision
Standardize `ruff` configurations across all workspace projects.
- **Line Length**: Increased to **100 characters** for better modern display utilization.
- **Tiered Linting**:
    - `src/` and `tests/`: Strict rules enabled (`E`, `F`, `I`, `N`, `W`, `B`, `UP`, `PL`, `RUF`).
    - `scripts/`, `scratch/`, `tools/`: Relaxed rules (ignore print statements, complexity, and line length) to allow rapid prototyping.
- **Formatting**: Unified `ruff format` usage without auto-fixes in CI.

## Consequences
### Positive
- Consistent code style across the workspace.
- Reduced noise in CI for non-core files.
- Improved readability of complex financial logic.
### Negative / Risks
- Requires developers to maintain local Ruff installations (mitigated by `uv` integration).

## References
- Tool: Ruff
- Config: `pyproject.toml` or `ruff.toml`
