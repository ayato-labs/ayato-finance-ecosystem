import concurrent.futures
from src.infra.tracing import trace_execution, current_trace_id, with_context
from src.engine import JPEDINETEngine


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
    engine = JPEDINETEngine()

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
                "sec_code": "T2",  # This will fail on INSERT
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

    from src.infra.db import db_manager

    with db_manager.connect_master() as conn:
        # We expect the batch to fail due to the None doc_id (NOT NULL constraint in real SQL,
        # or just DuckDB error). In our resilient implementation, it should fall back.
        engine._flush_results_to_db(conn, results)

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
