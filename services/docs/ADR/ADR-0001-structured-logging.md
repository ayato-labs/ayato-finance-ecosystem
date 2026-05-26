# ADR-0001: Standardized Structured Logging with Loguru

- **Date**: 2026-05-26
- **Status**: Accepted
- **Deciders**: Gemini CLI

## Context
Traceability and error analysis across multiple microservices were difficult due to inconsistent logging formats and lack of structured data. We needed a unified way to collect, rotate, and isolate errors across all Python-based financial services.

## Decision
Implement a standardized logging utility using `loguru` in `src/core/logging.py` for all services.
- **Format**: JSONL (Structured JSON per line) for machine readability.
- **Rotation**: Strict 2-run retention policy using timestamped filenames (`{app_name}_{time}.jsonl`).
- **Isolation**: Separate `error.log` for ERROR and CRITICAL levels.
- **Traceability**: Enabled full backtrace and diagnostic info in JSON output.

## Consequences
### Positive
- Unified log analysis across services.
- Automatic cleanup of old logs (storage efficiency).
- Faster debugging via isolated error files and rich context.
### Negative / Risks
- JSON logs are harder to read with plain `cat` or `type` (mitigated by retaining a simplified stderr handler).

## References
- Tool: Loguru
- Implementation: `src/core/logging.py`
