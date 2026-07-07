# ADR-0003: EDINET Rate Limiting and Ingestion Retry Strategy

- **Date**: 2026-06-04
- **Status**: Proposed
- **Deciders**: ayato-labs (human), Antigravity (Agent)

## Context
During historical backfilling, the ingestion pipeline encountered high rates of failures with the error:
`Document response does not appear to be a valid ZIP file`
Investigation showed that the EDINET API v2 returns an HTTP `200` OK response containing a JSON body:
`{"StatusCode":"429","message":"Too Many Requests"}`
when rate limits are triggered, instead of raising an HTTP `429` status code. 

Because of this:
1. `urllib.request` did not raise an `HTTPError`, passing the 429 JSON response as success.
2. `edinet_tools` client attempted to unzip the JSON response, leading to `BadZipFile` or formatting errors.
3. Multi-threaded ingestion (`max_workers=5`) fired requests too quickly, repeatedly triggering the 429 rate limit.
4. Failed attempts on `doc.parse()` were not retried, causing documents to be saved with missing narratives (silently failing narrative extraction).

## Decision
We will implement a resilient, rate-limit-aware ingestion strategy:
1. **Single-Threaded Ingestion by Default**: Change default `max_workers` from `5` to `1` across `sync_market` and `backfill_missing_data` to ensure requests are serialized.
2. **Rate-Limiting Delay**: Introduce a mandatory `time.sleep(1.5)` before any API-touching calls (`get_csv_from_edinet` and `doc.parse()`) to guarantee we respect the 1 request/second guideline.
3. **JSON 429 Detection**: Explicitly scan downloaded content for the signature `b'"StatusCode":"429"'` or `b'"Too Many Requests"'` inside `get_csv_from_edinet`. If detected, sleep with exponential backoff and retry.
4. **Resilient doc.parse() Wrapper with Retry**: Wrap `doc.parse()` in `_extract_narratives` with a retry loop (up to 3 attempts) utilizing exponential backoff for non-404 failures.

## Consequences
### Positive
- High resilience: Ingestion will automatically heal and retry when rate limits are triggered.
- Reduced API stress: Sequential execution with sleeps avoids triggering 429s in the first place.
- Eliminates silent failures of narrative extraction, ensuring data quality.

### Negative / Risks
- Total ingestion time per document increases slightly due to sequential delay. However, this is faster than the constant 60-second backoffs and process terminations caused by 429 loops.

## References
- ADR: [ADR-0002-raw-data-cache-policy.md](ADR-0002-raw-data-cache-policy.md)
