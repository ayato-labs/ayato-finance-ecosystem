# ADR-0006: EDINET Ingestion Resilience and Rate Limit Management

- **Date**: 2026-05-26
- **Status**: Accepted
- **Deciders**: Gemini CLI

## Context
The EDINET ingestion pipeline was failing due to high-volume errors including `ModuleNotFoundError` (missing `edinet_mcp`), `429 Too Many Requests` API limits, and `decimal.ConversionSyntax` crashes from malformed XBRL. These issues were compounded by multi-threading, where one thread hitting a rate limit would lead to a storm of errors across all workers.

## Decision
Implement a multi-layered resilience strategy for EDINET data ingestion:

1.  **Global Rate Limit Manager**: Introduced `src/datalake/shared/infra/rate_limit.py` to synchronize backoff across all worker threads. When one thread detects a `429` error, a global "stop-work" period (default 60s) is triggered for all active threads.
2.  **Fragile Dependency Wrapping**: Moved imports of external parsing libraries (e.g., `edinet_mcp`) inside parsing functions. This prevents a missing or broken library from causing a module-level `ImportError` that disables unrelated utilities.
3.  **Graceful Fact Extraction**: Wrapped internal XBRL fact extraction calls in specific `try-except` blocks. Data quality issues like `decimal.ConversionSyntax` are now logged as warnings, allowing the pipeline to skip the faulty document and continue rather than crashing the worker.
4.  **Signal vs. Noise Log Filtering**: Applied filters to BeautifulSoup and XML warnings to reduce log volume, ensuring that actual infrastructure or logic failures are not buried in data-specific noise.

## Consequences
### Positive
- **High Stability**: The pipeline can now process thousands of documents without human intervention, even when encountering malformed data.
- **API Politeness**: Automatically respects EDINET API limits, preventing long-term IP bans.
- **Traceability**: Precise identification of which documents failed due to data quality vs. system errors.
### Negative / Risks
- **Throughput Latency**: Global backoff reduces processing speed significantly during peak API usage (mitigated by long-term consistency).

## References
- Files: `src/datalake/service/ingestor.py`, `src/datalake/shared/infra/rate_limit.py`, `src/datalake/service/ensemble_parser.py`
