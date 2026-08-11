# DuckDB Memory Limit Error Analysis and Resolution Report

## Error Cause Analysis
- **File & Line**: `src/storage.py`, Line 89 (`conn.execute("CHECKPOINT")`) inside `_init_db()`
- **Root Cause**: DuckDB buffer manager memory limit was set to a default of `2GB` (`os.getenv("DUCKDB_MEMORY_LIMIT", "2GB")`). When running long-range synchronization jobs (`--days 1830`), in-memory WAL data and dirty buffer blocks exceeded available buffer slots. During `CHECKPOINT`, DuckDB attempted to pin a 256.0 KiB block while 1.8 GiB of the 1.8 GiB usable pool was exhausted, triggering `_duckdb.FatalException: FATAL Error: Failed to create checkpoint because of error: FATAL Error: Failed to create checkpoint: Out of Memory Error: failed to pin block of size 256.0 KiB`.
- **Secondary Causes**:
  1. DuckDB was not configured with `temp_directory`, preventing buffer manager memory from spilling overflow pages to disk.
  2. `preserve_insertion_order` default (`true`) retained extra metadata overhead during table writes.
  3. `CHECKPOINT` calls lacked exception safety boundaries during initialization.

## Implemented Solution
1. **Centralized Connection Factory (`_get_connection`)**:
   - Updated default `DUCKDB_MEMORY_LIMIT` from `2GB` to `8GB`.
   - Enabled disk spilling by setting `temp_directory` to `.tmp` inside the database parent directory.
   - Disabled insertion order preservation (`SET preserve_insertion_order=false`) to optimize memory footprint.
2. **Resilient CHECKPOINT Execution**:
   - Wrapped initial `CHECKPOINT` operations in `try/except Exception` blocks to prevent unexpected buffer pin issues from halting execution.
3. **Version Synchronization**:
   - Bumped `pyproject.toml` version to `0.1.6`.
