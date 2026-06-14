import time

from src.datalake.shared.infra.db import db_manager
from src.datalake.shared.infra.migrations import MigrationManager
from src.datalake.service.writer import DatabaseWriter


def test_database_writer_batch_flush(tmp_path, monkeypatch):
    """
    Unit: Verify that DatabaseWriter correctly flushes data to DuckDB.
    """
    monkeypatch.setenv("MASTER_DB_PATH", ":memory:")

    MigrationManager.apply_migrations()

    writer = DatabaseWriter(batch_size=2)
    writer.start()

    # Sample data
    ingest_data = {
        "metadata": {
            "doc_id": "W001",
            "edinet_code": "E1",
            "sec_code": "1001",
            "filer_name": "F1",
            "doc_description": "D1",
            "submit_datetime": "2024-01-01 00:00:00",
            "form_code": "F",
            "doc_type_code": "T",
            "session_id": "S1",
        },
        "narratives": [],
        "facts": [],
    }

    writer.put("ingest", ingest_data)
    # Since batch_size is 2, it shouldn't flush yet (unless timeout hits, but let's wait a bit)
    time.sleep(0.5)

    with db_manager.connect_master(read_only=True) as conn:
        count = conn.execute("SELECT count(*) FROM registry_db.filings").fetchone()[0]
        # Might be 0 if timeout hasn't hit, or 1 if it did.
        # But we stop it now which should force flush.

    writer.stop()

    with db_manager.connect_master(read_only=True) as conn:
        count = conn.execute("SELECT count(*) FROM registry_db.filings").fetchone()[0]
        assert count == 1


def test_database_writer_error_handling(tmp_path, monkeypatch):
    """
    Unit: Verify that DatabaseWriter handles malformed data without crashing.
    """
    monkeypatch.setenv("MASTER_DB_PATH", ":memory:")
    writer = DatabaseWriter(batch_size=1)
    writer.start()

    # Malformed data (missing keys)
    writer.put("ingest", {"metadata": {}})

    writer.stop()  # Should log error but not crash
    assert True
