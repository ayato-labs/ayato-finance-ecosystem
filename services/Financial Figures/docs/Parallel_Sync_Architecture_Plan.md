# Implementation Plan: Parallel Sync Architecture (Multi-Source)

## 1. Executive Summary
The current `BatchSyncService` uses a single `db_queue` and a single `DBWriter` thread for all database writes (US, JP, EDINET). While DuckDB requires single-writer access *per database file*, our architecture uses physically separated files (`us.duckdb`, `jp.duckdb`, `edinet.duckdb`). Therefore, enforcing a global write lock across all markets creates an artificial bottleneck.

This plan details the refactoring required to establish true parallel synchronization, utilizing independent queues and writer threads for each market, while maintaining a unified AI mapping queue.

## 2. Architectural Changes

### 2.1 Queue Segregation
- **Current:** 1 `db_queue`
- **New:** 
  - `us_db_queue` (consumed by `us_db_worker`)
  - `jp_db_queue` (consumed by `jp_db_worker`)
  - `edinet_db_queue` (consumed by `edinet_db_worker`)
  - `audit_db_queue` (consumed by `audit_worker` for traceability/session logs to avoid locking market DBs during audit writes)

### 2.2 Offloading Tag Discovery
- **Current Bottleneck:** `_queue_unmapped_tags` runs synchronously inside `_process_db_task`, pausing database ingestion for ~0.24s per ticker.
- **New:** Tag discovery will be moved to a dedicated `TagDiscoveryWorker` or pushed asynchronously from the Fetcher threads *after* they successfully fetch data, decoupling it from the fast-path ingestion loop.

### 2.3 EDINET Integration
- **Current:** `EDINETSyncWorker` runs sequentially and blocks the main thread during execution. AI mapping happens inline during sync.
- **New:** Integrate EDINET into the `BatchSyncService`. The EDINET fetcher will push facts to `edinet_db_queue` and unknown tags to the unified `ai_queue`.

## 3. Implementation Steps

### Phase 1: Service Structure Overhaul (Target: `src/services/market_sync.py`)
1. **Initialize Segregated Queues:** Update `BatchSyncService.__init__` to create market-specific queues.
2. **Spawn Independent DB Writers:** Create dedicated worker methods (e.g., `_us_db_worker`, `_jp_db_worker`) that only write to their respective DuckDB connections.
3. **Audit Isolation:** Route all `audit_manager` calls through a dedicated `audit_db_queue` so market ingestion doesn't wait on `traceability.duckdb` locks.

### Phase 2: Unblocking the Ingestion Path
1. **Refactor Tag Discovery:** Remove `_queue_unmapped_tags` from the DB writer loop. 
2. **Implementation:** Have the DB Writer emit a `TAG_DISCOVERY_REQUEST` event to a background worker once ingestion is complete, or pre-calculate it in the fetcher thread.

### Phase 3: Concurrent Orchestration
1. **Modify `sync_market_full`:** Update the orchestration method to accept concurrent execution. If `--sync-market all` is passed, use `concurrent.futures.ThreadPoolExecutor` at the top level to fire `_sync_us_market`, `_sync_jp_market`, and `_sync_edinet_market` simultaneously.
2. **EDINET Worker Integration:** Adapt `EDINETSyncWorker` to act as a fetcher that pushes to the new queue architecture rather than writing directly to DB/AI.

### Phase 4: Validation & Stabilization
1. **Run Benchmarks:** Use `scratch/profile_sync_bottlenecks.py` to verify that DB write latency and tag discovery no longer block one another.
2. **Integration Tests:** Ensure `test_sync_integration.py` and chaos tests pass with the new concurrent architecture.

## 4. Expected Outcomes
- **Throughput:** US and EDINET syncs will complete significantly faster, no longer bottlenecked by the mandatory 12.5s wait times of the J-Quants API.
- **Resource Utilization:** CPU cores will be utilized more efficiently as network I/O, DB I/O, and AI mapping happen concurrently across independent pipelines.
- **Stability:** Complete elimination of cross-database lock contention (e.g., US DB locked while JP data is waiting in a unified queue).
