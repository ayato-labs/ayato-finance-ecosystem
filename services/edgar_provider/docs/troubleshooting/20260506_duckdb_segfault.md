# Troubleshooting: DuckDB C-level Segmentation Fault during Bulk Ingestion

## Symptom
During bulk data ingestion (EDGAR bulk ZIP parsing), the Python process suddenly terminates with a C-level segmentation fault or "Press any key to continue..." without a Python traceback. This typically occurs after processing several batches.

## Environment
- OS: Windows
- DB: DuckDB
- Data Library: Pandas / PyArrow

## Cause
**DuckDB ART Index Corruption during UPSERTs**
The root cause is a bug in DuckDB's Adaptive Radix Tree (ART) implementation on Windows. When performing high-throughput `INSERT OR REPLACE` (UPSERT) operations on a table that has **secondary indexes**, DuckDB's internal memory management for the ART index can fail during reallocation, leading to a memory access violation (segmentation fault).

Additionally, direct in-memory registration of Arrow tables (`conn.register`) can occasionally cause pointer conflicts between the Python garbage collector and DuckDB's internal thread pool.

## Solution

### 1. Index Lifecycle Management
Before starting a bulk ingestion, all secondary indexes on the target tables must be dropped. They should only be re-created after the ingestion is complete.
```sql
-- Before ingestion
DROP INDEX IF EXISTS idx_filings_ticker;
DROP INDEX IF EXISTS idx_us_facts_lookup;

-- After ingestion
CREATE INDEX IF NOT EXISTS idx_filings_ticker ON filings (ticker);
CREATE INDEX IF NOT EXISTS idx_us_facts_lookup ON company_facts (accession_number, fiscal_year, fiscal_period);
```

### 2. Physical Staging (Parquet-based)
To eliminate memory pointer conflicts, data should be serialized to disk as Parquet files and then loaded into DuckDB using the `read_parquet()` function. This ensures that DuckDB's C++ engine handles the file I/O independently of the Python object lifecycle.

### 3. Serialized Writer (Producer-Consumer)
Use a dedicated background thread for DuckDB writes to ensure serial execution. Use a thread-safe queue with a size limit (backpressure) to prevent the JSON parser threads (Producers) from overwhelming the database writer (Consumer) and causing memory exhaustion.

### 4. Periodic Checkpoints
Execute `PRAGMA checkpoint;` every 5-10 batches to flush the Write-Ahead Log (WAL) and stabilize memory usage.

## Prevention
- **Never perform bulk UPSERTs on tables with active secondary indexes in DuckDB.**
- Prefer `read_parquet` or `read_csv` over direct Arrow registration for large datasets.
- Always implement a serial writer when multiple threads are parsing data for a single DuckDB database.
