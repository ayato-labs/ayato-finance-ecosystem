import threading
import time

import duckdb
import pytest

from loguru import logger
from edgar_core.config import settings
from edgar_core.db import db_manager
from edgar_provider\.engine import USEngine


def test_chaos_db_locking():
    """Chaos Test: Multiple threads competing for the same database."""
    db_path = settings.FACTS_DB_PATH
    USEngine()  # Triggers migration

    errors = []

    def heavy_writer():
        try:
            with db_manager.connect(db_path, timeout_seconds=5) as conn:
                for i in range(100):
                    conn.execute(
                        "INSERT INTO metrics (run_id, step_name, status) VALUES (?, ?, ?)",
                        [f"chaos-{i}", "chaos_step", "success"]
                    )
                    time.sleep(0.01)  # Hold lock briefly
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=heavy_writer) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # We expect our DuckDBManager to handle retries and succeed
    assert len(errors) == 0, f"Encountered {len(errors)} locking errors: {errors}"

def test_chaos_malformed_json_bulk():
    """Chaos Test: Ingesting malformed JSON strings in bulk process."""
    from edgar_provider\.engine import parse_company_facts_json

    # Should not crash, should return empty lists (per our robust try-except)
    filings, facts = parse_company_facts_json(
        "corrupt.json", "{ 'invalid': json ...", {"123": "FAKE"}, "chaos-session"
    )
    assert filings == []
    assert facts == []

def test_chaos_null_primary_keys():
    """Chaos Test: Attempting to save records with NULL in Primary Key columns."""
    from edgar_core.contracts import USFactContract, USFilingContract
    from pydantic import ValidationError
    engine = USEngine()

    bad_filings = []
    bad_facts = []

    # 1. Test Pydantic protection (Controlled failure)
    try:
        bad_filings.append(USFilingContract(accession_number=None, ticker="AAPL", cik="320193", form="10-K", filed_date="2024-01-01", session_id="sid"))
    except ValidationError:
        logger.debug("Pydantic caught null accession_number correctly.")

    try:
        bad_facts.append(USFactContract(accession_number="accn", fiscal_year=2023, fiscal_period="FY", label=None, value=1.0, unit="USD", is_standardized=True, raw_tag="tag"))
    except ValidationError:
        logger.debug("Pydantic caught null label correctly.")

    # 2. Even if we bypass Pydantic somehow (e.g. raw dicts), _save_facts should handle it or fail gracefully
    try:
        engine._save_facts(bad_filings, bad_facts)
    except Exception as e:
        logger.debug(f"Save failed as expected: {e}")

    with db_manager.connect(engine.facts_db) as conn:
        count = conn.execute("SELECT count(*) FROM company_facts").fetchone()[0]
        assert count == 0
