# ADR-0002: Raw Data Ingestion Cache Policy

- **Date**: 2026-06-04
- **Status**: Accepted
- **Deciders**: ayato-labs (human), Antigravity (Agent)

## Context
The EDINET ingestion pipeline fetched ZIP files containing CSV raw data for target documents and cached them locally compressed with Zstandard (`.zip.zst`) in `data/datalake/raw`. 
However, running a full 5-year historical backfill consumes a significant amount of local SSD space. 
We analyzed options to either:
1. Move the cache to Google Drive.
2. Completely abandon raw ZIP file caching to save SSD space and reduce write degradation.

## Decision
We decided to **completely eliminate all raw ZIP file caching code and delete the raw directory** from the codebase:
1. We will remove all references to `RAW_DATA_DIR` and `RAW_CACHE_ENABLED` from configuration settings.
2. We will strip the `RawCacheWriter` and raw file caching logic out of `csv_parser.py`, `writer.py`, and `ingestor.py` completely.
3. The ingestion pipeline will keep raw file streams entirely in-memory, performing CSV extraction directly from the retrieved HTTP responses.
4. The `data/datalake/raw/` directory will be deleted.

### Rationale
- **Virtual Source of Truth**: The EDINET API is a stable, government-operated endpoint that keeps historical documents available permanently. The API acts as a virtual "bronze" layer, so keeping local copies of historical ZIP files is redundant.
- **Form Code Filtering Efficiency**: Since we already limited ingestion to 6 primary financial report form codes (reducing document candidate volumes by ~80%), any future database repair or schema migration will only need to download a small fraction of documents, mitigating API rate-limiting issues during re-runs.
- **SSD Protection and Code Simplicity**: Removing raw caching code completely simplifies the codebase, eliminates the need for Zstandard compression during ingestion, and ensures that the local SSD is completely protected from transient write cycles.

## Consequences
### Positive
- Zero local SSD space consumed by raw zip/zst files.
- Faster execution speeds during ingestion due to reduced disk I/O and no compression overhead.
- Much cleaner, simpler codebase with fewer classes, arguments, and settings to manage.

### Negative / Risks
- If we need to re-parse or rebuild the database from scratch, we must pull documents from the EDINET API again, which consumes API quota. This is mitigated by our 6-form filter and rate-limiting/retry updates (see ADR-0003).

## References
- ADR: [ADR-0001-limit-ingestion-to-financial-reports.md](ADR-0001-limit-ingestion-to-financial-reports.md)
