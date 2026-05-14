import concurrent.futures

from src.infra.db import db_manager
from src.infra.migrations import MigrationManager
from src.infra.tracing import current_trace_id, trace_execution, with_context
from src.service.writer import DatabaseWriter


def test_trace_id_propagation_to_threads():
    """
    Severe Test (SRE): Verify TraceID propagates to ThreadPoolExecutor workers.
    """

    @trace_execution
    def parent_task():
        parent_id = current_trace_id.get()

        def child_task():
            return current_trace_id.get()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            # Using with_context wrapper
            future = executor.submit(with_context(child_task))
            child_id = future.result()

        return parent_id, child_id

    pid, cid = parent_task()
    assert pid != "root"
    assert pid == cid, "TraceID did not propagate to worker thread!"


def test_engine_batch_partial_success(tmp_path, monkeypatch):
    """
    Severe Test (Architect): Verify that 1 bad record doesn't roll back the whole batch.
    """
    monkeypatch.setenv("MASTER_DB_PATH", ":memory:")
    
    # Run migrations first
    MigrationManager.apply_migrations()

    writer = DatabaseWriter()

    # Mock results: 1 good, 1 bad (missing doc_id), 1 good
    results = [
        {
            "metadata": {
                "doc_id": "GOOD_1",
                "edinet_code": "E1",
                "sec_code": "T1",
                "filer_name": "F1",
                "doc_description": "D1",
                "submit_datetime": "2024-01-01",
                "form_code": "C1",
                "doc_type_code": "T1",
                "session_id": "S1",
            },
            "narratives": [],
            "facts": [],
        },
        {
            "metadata": {
                "doc_id": None,
                "edinet_code": "E2",
                "sec_code": "T2",
                "filer_name": "F2",
                "doc_description": "D2",
                "submit_datetime": "2024-01-01",
                "form_code": "C2",
                "doc_type_code": "T2",
                "session_id": "S2",
            },
            "narratives": [],
            "facts": [],
        },
        {
            "metadata": {
                "doc_id": "GOOD_2",
                "edinet_code": "E3",
                "sec_code": "T3",
                "filer_name": "F3",
                "doc_description": "D3",
                "submit_datetime": "2024-01-01",
                "form_code": "C3",
                "doc_type_code": "T3",
                "session_id": "S3",
            },
            "narratives": [],
            "facts": [],
        },
    ]

    with db_manager.connect_master() as conn:
        # We expect the batch to fail due to the None doc_id.
        # In our resilient implementation, it should fall back.
        writer._flush_results_to_db(conn, results)

        # Verify GOOD_1 and GOOD_2 are there (fresh DB due to reset fixture)
        ids = [
            r[0]
            for r in conn.execute(
                "SELECT doc_id FROM registry_db.filings ORDER BY doc_id"
            ).fetchall()
        ]
        assert "GOOD_1" in ids
        assert "GOOD_2" in ids
        assert len(ids) == 2
