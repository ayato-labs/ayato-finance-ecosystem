import sys

from loguru import logger

from src.core.audit_manager import audit_manager
from src.core.logging import setup_logging
from src.engines.us_engine import USEngine

# Initialize logging
setup_logging()


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
                logger.error(msg)
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

    except Exception as e:
        # 3. Close Session (Critical Failure)
        logger.exception(f"CRITICAL ERROR during US Sync: {e}")
        audit_manager.end_session(
            session_id=session_id,
            status="FAILED",
            records=records_processed,
            errors=errors_count + 1,
            error_log=str(e),
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
