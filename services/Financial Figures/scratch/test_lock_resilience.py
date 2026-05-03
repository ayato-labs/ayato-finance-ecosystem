import logging
import multiprocessing
import sys
import time
from pathlib import Path

import duckdb

# Add project root to path for local imports
sys.path.append(str(Path(__file__).parent.parent))
from src.core.audit_manager import AuditManager

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ChaosTest")


def lock_holder(db_path, lock_event, release_event):
    """Process A: Intentionally holds the lock."""
    # Process-specific logger setup
    logger = logging.getLogger("LockHolder")
    logger.info("Connecting to DB and starting exclusive lock...")
    try:
        # On Windows, opening a write connection locks the file
        conn = duckdb.connect(str(db_path))
        logger.info("LOCK ACQUIRED. Holding for 7 seconds...")
        lock_event.set()
        time.sleep(7)
        logger.info("Releasing lock now.")
        conn.close()
    except Exception as e:
        logger.error(f"Error in lock_holder: {e}")
    finally:
        release_event.set()


def resilient_worker(db_path, lock_event):
    """Process B: Tries to write using our hardened logic."""
    logger = logging.getLogger("ResilientWorker")
    manager = AuditManager(db_path=db_path)

    # Wait until process A has the lock
    while not lock_event.is_set():
        time.sleep(0.1)

    logger.info("Starting write attempt during lock...")
    start_time = time.perf_counter()
    try:
        manager.log_mapping(
            session_id="chaos-session",
            source_tag="CHAOS:TEST",
            mapped_label="STRESS_RECOVERY",
            reasoning="Verification of high-resiliency locking logic",
            model="ChaosTesterV1",
        )
        duration = time.perf_counter() - start_time
        logger.info(f"SUCCESS! Write completed in {duration:.2f}s after recovery.")
    except Exception as e:
        logger.error(f"FAILED: {e}")


def run_chaos_test():
    db_path = Path("data/audit/chaos_test.duckdb")
    if db_path.exists():
        db_path.unlink()

    # Use multiprocessing shared primitives
    lock_event = multiprocessing.Event()
    release_event = multiprocessing.Event()

    p1 = multiprocessing.Process(target=lock_holder, args=(db_path, lock_event, release_event))
    p2 = multiprocessing.Process(target=resilient_worker, args=(db_path, lock_event))

    p1.start()
    p2.start()

    p1.join()
    p2.join()

    # Final check
    logger.info("Verifying data persistence in chaos DB...")
    conn = duckdb.connect(str(db_path), read_only=True)
    res = conn.execute(
        "SELECT mapped_label FROM mapping_audit WHERE source_tag='CHAOS:TEST'"
    ).fetchone()
    if res and res[0] == "STRESS_RECOVERY":
        logger.info("--- TEST PASSED: Resiliency Hardening Verified ---")
    else:
        logger.error("--- TEST FAILED: Data not found! ---")


if __name__ == "__main__":
    run_chaos_test()
