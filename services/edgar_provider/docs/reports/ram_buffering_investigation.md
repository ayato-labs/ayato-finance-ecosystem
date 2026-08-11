# Detailed Investigation: DB Batch Buffering & Memory Limit Bypass

## Executive Summary

Further deep-code investigation revealed two critical memory issues during delta update execution:

1. **Complete Bypass of DuckDB Memory Limits (`_get_connection` Bug)**
   `EdgarStorage` defined `_get_connection()` to apply `DUCKDB_MEMORY_LIMIT`, `temp_directory`, and `preserve_insertion_order=false`.
   However, **every single database method** (`save_filings_batch`, `save_facts_batch`, `filing_exists_batch`, `facts_exist_batch`, etc.) called `duckdb.connect(self.db_path)` directly instead of `self._get_connection()`.
   As a result, DuckDB executed all batch saves and queries with **uncapped system memory** and **no disk-spilling temporary directory**, completely ignoring configured memory limits.

2. **Impact of In-Memory Batch Buffering (`BATCH_SIZE=10/20`)**
   The user's hypothesis is **correct**. Buffering 10 to 20 filings in the Python `buffer` list inside `_filings_db_consumer` retains 10 to 20 full 10-K parsed section dictionaries (each containing 10MB–50MB of markdown text strings) in Python heap memory simultaneously.
   Because DuckDB executes writes efficiently on local connections, buffering 10-20 large text documents in RAM delays Python garbage collection without providing significant I/O benefits.

---

## Detailed Findings

### 1. `EdgarStorage` Connection Factory Bypass
- **Location**: `src/storage.py` (lines 409, 450, 471, 505, 525, 535, 549, 565, 587, etc.)
- **Defect**:
  ```python
  # Defined in storage.py but NEVER called by data methods:
  def _get_connection(self):
      conn = duckdb.connect(self.db_path)
      conn.execute(f"SET memory_limit='{memory_limit}'")
      conn.execute(f"SET temp_directory='{temp_dir.as_posix()}'")
      ...
      return conn

  # Actual implementation in save_filings_batch, save_facts_batch, etc.:
  with duckdb.connect(self.db_path) as conn:  # Bypassed memory limit & temp dir!
  ```
- **Consequence**: DuckDB allocated unconstrained system RAM during all data ingestion steps.

### 2. Python Heap Memory Retention in `_filings_db_consumer`
- **Location**: `src/pipeline.py` (lines 20-39, 42-61)
- **Defect**:
  ```python
  buffer.append(item)
  if len(buffer) >= BATCH_SIZE:  # Retains BATCH_SIZE large text items in Python RAM
      await asyncio.to_thread(storage.save_filings_batch, list(buffer))
      buffer.clear()
  ```
- **Consequence**: Holding 10-20 full filing section dictionaries in a Python `list` pins hundreds of megabytes in Python process heap until `len(buffer)` reaches `BATCH_SIZE`.
- **Solution**: Replace `duckdb.connect` calls with `self._get_connection()`, and reduce `BATCH_SIZE` to `1` or `2` so text objects are garbage collected immediately after writing to DuckDB.

---

## Recommended Remediation Plan

1. Update all `duckdb.connect(self.db_path)` invocations in `src/storage.py` to `self._get_connection()`.
2. Change `BATCH_SIZE` default from `10` to `1` (or `2`) in `src/pipeline.py` and `.env.example` so Python releases section text immediately after saving each filing.
3. Explicitly delete buffer items and invoke `gc.collect()` in consumer loops.
