# SEC EDGAR Provider RAM Usage Investigation Report

## Executive Summary

When executing the delta update logic (`sync` / `ticker` command), RAM usage surges up to 10GB.
This investigation identified 4 primary root causes contributing to the excessive RAM consumption:

1. **Unbounded Concurrency for Facts Extraction Background Tasks**
2. **Excessive `asyncio.Queue` Buffer Sizes for HTML Data**
3. **High Default DuckDB Memory Limit (`8GB`)**
4. **Memory Footprint of BeautifulSoup / lxml DOM Trees and Garbage Collection Timing**

---

## Technical Cause Breakdown

### 1. Unbounded Concurrency in `_extract_and_queue_facts`
- **Location**: `src/pipeline.py` (lines 233-240, 358-365)
- **Mechanism**: In `sync_recent_us_filings` and `process_us_tickers`, `_extract_and_queue_facts` tasks are created using `asyncio.create_task()` for every target accession number without concurrency throttling.
- **Impact**: When syncing dozens or hundreds of filings, hundreds of XBRL fetching and pandas DataFrame extraction tasks execute in parallel. Each `edgartools` / pandas call allocates tens of megabytes, creating a massive RAM spike (3GB - 5GB+).

### 2. Large `asyncio.Queue` Buffer Capacity (`maxsize=200`)
- **Location**: `src/pipeline.py` (lines 158-160, 282-284)
- **Mechanism**: `raw_queue`, `filings_queue`, and `facts_queue` are configured with `maxsize=200`.
- **Impact**: SEC 10-K HTML documents can range from 10MB to 50MB per file. Buffering up to 200 raw HTML files in memory concurrently requires 2GB to 5GB of Python heap memory. Buffering parsed sections and DataFrames in parallel queues further escalates memory usage.

### 3. DuckDB Memory Throttling Defaults (`8GB`)
- **Location**: `src/storage.py` (line 49)
- **Mechanism**: `DUCKDB_MEMORY_LIMIT` defaults to `8GB`.
- **Impact**: DuckDB buffer manager allocates and holds up to 8GB of process memory for query execution, index lookup, and WAL operations before spilling pages to disk. When combined with Python heap objects, total process memory easily exceeds 10GB.

### 4. DOM Tree Memory Overhead in `BeautifulSoup` & `lxml`
- **Location**: `src/parser.py` (line 111)
- **Mechanism**: `BeautifulSoup(html_content, "lxml")` creates in-memory element tree nodes.
- **Impact**: Parsing a 30MB HTML file constructs a DOM tree that consumes 150MB - 300MB of RAM per worker thread. With 4 concurrent parse workers and high throughput, memory allocations compound before Python garbage collection reclaims unreferenced nodes.

---

## Proposed Remediation Strategies

| Issue Component | Current State | Proposed Optimizations | Expected RAM Reduction |
| :--- | :--- | :--- | :--- |
| **Facts Extraction Throttling** | Unbounded `create_task()` | Throttle with `asyncio.Semaphore(4)` or bounded queue | ~3.0 GB - 4.0 GB |
| **Queue Capacity** | `maxsize=200` (~4GB RAM) | Reduce to `maxsize=20` (~200MB - 400MB RAM) | ~2.0 GB - 3.5 GB |
| **DuckDB Memory Limit** | `DUCKDB_MEMORY_LIMIT=8GB` | Lower default to `2GB` (with disk temp spilling) | ~4.0 GB - 6.0 GB ceiling reduction |
| **Garbage Collection Policy** | Default Python GC | Explicit `gc.collect()` after large batch operations | ~500 MB |

---

## Next Steps

1. Create Architecture Decision Record (ADR) for RAM optimization strategy.
2. Update pipeline queue sizes and semaphore controls.
3. Validate memory efficiency using test suite and load simulation.
