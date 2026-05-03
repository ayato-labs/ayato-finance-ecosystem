import logging
import sys
import traceback

from src.core.audit_manager import audit_manager
from src.engines.us_engine import USEngine

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def main():
    logger.info("=== Financial Figures: US Market Sync with Traceability ===")

    # 0. Start Audit Session
    session_id = audit_manager.start_session(market="US")
    logger.info(f"Audit Session Started: {session_id}")

    us_engine = USEngine()
    records_processed = 0
    errors_count = 0
    error_summary = []

    try:
        # 1. Sync Metadata
        logger.info("Syncing Ticker-CIK mappings from SEC...")
        count = us_engine.sync_tickers(session_id)
        logger.info(f"Success: {count} tickers available in DuckDB.")

        # 2. Sync Fundamentals (Prototype Target)
        test_tickers = ["AAPL", "MSFT", "NVDA", "TSLA"]
        for ticker in test_tickers:
            logger.info(f"Processing {ticker}...")
            try:
                facts = us_engine.fetch_company_facts(ticker)
                if facts:
                    us_engine.ingest_facts(ticker, facts, session_id)
                    logger.info(f"Successfully ingested concepts for {ticker}.")
                    records_processed += 1
                else:
                    logger.warning(f"Skipped {ticker}: No data returned.")
            except Exception as e:
                errors_count += 1
                msg = f"Error processing {ticker} (US): {e!s}"
                logger.error(msg, exc_info=True)
                error_summary.append(msg)

        # 3. Close Session (Success)
        audit_manager.end_session(
            session_id=session_id,
            status="SUCCESS" if errors_count == 0 else "PARTIAL",
            records=records_processed,
            errors=errors_count,
            error_log="\n".join(error_summary) if error_summary else None,
        )
        logger.info("US Sync Complete.")

    except Exception:
        # 3. Close Session (Critical Failure)
        full_error = traceback.format_exc()
        logger.critical(f"CRITICAL ERROR: {full_error}")
        audit_manager.end_session(
            session_id=session_id,
            status="FAILED",
            records=records_processed,
            errors=errors_count + 1,
            error_log=full_error,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
