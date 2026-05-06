# Future Prospect: Historical Data Parquetization Strategy

To further optimize storage efficiency and maintain high performance for the active DuckDB shards, we propose a strategy for migrating "old" data to the Apache Parquet format.

## 1. Rationale
While DuckDB is highly efficient for active workloads, as the dataset grows over multiple years, moving historical, immutable data to Parquet offers several advantages:
- **Extreme Compression**: Parquet's columnar storage and encoding techniques typically achieve better compression than standard SQL formats for historical data.
- **Cold Storage Architecture**: Parquet files can be stored on cheaper object storage (e.g., S3, Azure Blob Storage) while remaining queryable via DuckDB.
- **Resource Isolation**: Reducing the size of the active `.duckdb` shards minimizes memory footprint and backup times.

## 2. Archiving Criteria
We recommend the following criteria for "Old Data":
- **Filings Metadata**: Records older than 3 years.
- **Company Facts**: Historical numerical data for companies that have not filed in over 2 years.
- **Narratives**: Unstructured text blocks for filings older than 2 years (these are the largest records).

## 3. Implementation Steps

### Phase A: Identification
Identify records eligible for archiving based on the `submit_datetime` or `ingested_at` columns.

### Phase B: Extraction (DuckDB to Parquet)
Utilize DuckDB's native Parquet support to export data efficiently:
```sql
COPY (
    SELECT * FROM narr_db.narratives 
    WHERE ingested_at < CURRENT_DATE - INTERVAL '2 years'
) TO 'data/archives/narratives_2023.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
```

### Phase C: Deletion & Vacuum
Remove the archived records from the active shards and reclaim space:
```sql
DELETE FROM narr_db.narratives 
WHERE ingested_at < CURRENT_DATE - INTERVAL '2 years';
VACUUM;
```

### Phase D: Hybrid Querying (Optional)
Implement a "Unified View" in DuckDB that joins active SQL data with historical Parquet data for seamless analysis:
```sql
CREATE VIEW all_narratives AS
SELECT * FROM narr_db.narratives
UNION ALL
SELECT * FROM read_parquet('data/archives/*.parquet');
```

## 4. Maintenance
Archiving should be scheduled as an annual or quarterly maintenance task (e.g., `JPEDINETEngine.archive_historical_data()`).
