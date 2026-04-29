# Operational Guide

This document covers the ongoing maintenance and reliability strategies for the Ayato Finance Ecosystem.

## 💾 Database Management
The ecosystem uses a distributed file-based storage model (DuckDB).

### Backup Strategy
Since databases are local `.duckdb` files, standard file backups are sufficient.
- **Recommended**: Daily snapshot of `assets.duckdb` and `jp.duckdb`.
- **Note**: Ensure the API servers are stopped or in `--read-only` mode during the copy to prevent corruption.

### Data Integrity
If a DuckDB file becomes corrupted due to a system crash:
1. Delete the `.duckdb` file.
2. Re-run the relevant ingestion engine (`run_sync.bat` or `run_full_backfill.bat`).
3. Since the raw data is fetched from APIs (J-Quants, EDINET, etc.), the state is reproducible.

## 📜 Log Management
Logs are stored using `loguru` in the `logs/` directory of each module.
- **Retention**: Each log file is rotated at 10 MB.
- **Monitoring**: Check `backend_error.log` for validation errors (422) or API timeouts.

## ⚙️ Resource Monitoring
- **Memory**: Analytical queries on the US market may require 4GB+ of free RAM depending on the time range.
- **Disk**: A full backfill of Japanese and US market data can grow to several gigabytes. Monitor disk space in the project root.
