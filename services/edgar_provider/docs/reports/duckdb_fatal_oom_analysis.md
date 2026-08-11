# DuckDB Fatal Invalidation and Buffer Manager OOM Analysis

## Error Summary

```text
Error saving filing 0001104659-26-093061: FATAL Error: Failed: database has been invalidated because of a previous fatal error. The database must be restarted prior to being used again.
Original error: Out of Memory Error: could not allocate block of size 23.7 MiB (1.8 GiB/1.8 GiB used)
```

---

## Root Cause Analysis

### 1. DuckDB Internal Buffer Pool Starvation (`DUCKDB_MEMORY_LIMIT=2GB`)
- **Mechanism**: Setting `DUCKDB_MEMORY_LIMIT=2GB` restricts DuckDB's C++ buffer manager to ~1.8 GiB usable memory.
- **Trigger**: When saving large filings (such as 10-K filing `0001104659-26-093061`), DuckDB attempts to allocate text blocks (e.g. 23.7 MiB) for uncompressed `content_md` strings in `filing_sections`. When buffer slots are exhausted at 1.8 GiB, DuckDB fails to pin the memory block.
- **Result**: DuckDB aborts the transaction and invalidates the database connection.

### 2. Invalidated Connection Cascade in Batch Operations
- **Location**: `src/storage.py` (`save_filings_batch`, `save_facts_batch`)
- **Mechanism**: A single `conn` is opened for the batch loop.
- **Trigger**: When `_insert_single_filing` throws a fatal DuckDB error, `conn` enters an invalidated state.
- **Result**: The `try...except` block catches the exception, but the loop continues trying to execute queries on the same invalidated `conn`, logging `FATAL Error: database has been invalidated` for every remaining item in the batch.

### 3. Balance Between Python Heap Optimization and DuckDB Buffer Pool
- **Insight**: Restricting `DUCKDB_MEMORY_LIMIT` to `2GB` confused Python process heap limit with DuckDB internal C++ buffer pool limit.
- **Solution**:
  - Python process heap is controlled by `raw_queue(maxsize=20)`, `facts_semaphore(4)`, and `BATCH_SIZE=1`.
  - DuckDB buffer pool needs sufficient headroom (`4GB`) so it never starves during 20MB–50MB string block allocations.

---

## Resolution Strategy

1. **Adjust Default DuckDB Memory Limit**: Change default `DUCKDB_MEMORY_LIMIT` from `2GB` to `4GB` in `storage.py` and `.env.example`.
2. **Resilient Connection & Re-connection Handling**:
   - In `save_filings_batch` and `save_facts_batch`, if a fatal DuckDB error or invalidated connection error occurs, catch the exception, close the invalidated connection, re-open a fresh connection via `self._get_connection()`, and continue processing remaining items safely.
3. **Emergency CHECKPOINT & Recovery**: Call `conn.execute("CHECKPOINT")` safely and handle transient errors gracefully.
