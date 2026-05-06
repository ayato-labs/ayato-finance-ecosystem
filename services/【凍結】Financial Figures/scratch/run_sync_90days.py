import sys
import os
from datetime import date

# Add project root to path
sys.path.append(os.getcwd())

from src.edinet.sync_worker import EDINETSyncWorker

def main():
    print("=== Starting 90-Day Incremental Sync ===")
    worker = EDINETSyncWorker()
    
    # Run backfill for the last 90 days
    # This will force the range regardless of last sync date
    worker.run_backfill(days=90)
    
    print("=== Sync Operation Triggered ===")

if __name__ == "__main__":
    main()
