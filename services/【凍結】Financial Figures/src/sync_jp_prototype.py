import sys
import traceback

from dotenv import load_dotenv

from src.core.audit_manager import audit_manager
from src.providers.jquants.engine import JPEngine


def main():
    load_dotenv()
    print("=== Financial Figures: JP Market Sync (J-Quants V2) ===")

    # 0. Start Audit Session
    session_id = audit_manager.start_session(market="JP")
    print(f"Audit Session Started: {session_id}")

    try:
        engine = JPEngine()

        # 1. Sync Tickers
        print("Syncing JP Tickers...")
        count = engine.sync_tickers(session_id)
        print(f"Success: {count} tickers synced.")

        # 2. Sync Fundamentals (Prototype Target)
        # 8697 (JPX), 7203 (Toyota), 9984 (SoftBank), 6758 (Sony)
        jp_tickers = ["8697", "7203", "9984", "6758"]

        records_processed = 0
        for code in jp_tickers:
            print(f"\nProcessing {code}...")
            try:
                engine.fetch_and_ingest_statements(code, session_id)
                print(f"Successfully processed {code}.")
                records_processed += 1
            except Exception as e:
                print(f"Error processing {code}: {e}")

        # 3. End Session
        audit_manager.end_session(session_id, "SUCCESS", records_processed, 0)
        print("\nJP Sync Prototype Complete.")

    except Exception:
        full_error = traceback.format_exc()
        print(f"CRITICAL ERROR: {full_error}")
        audit_manager.end_session(session_id, "FAILED", 0, 1, full_error)
        sys.exit(1)


if __name__ == "__main__":
    main()
