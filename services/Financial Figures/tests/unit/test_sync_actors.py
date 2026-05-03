import duckdb

from src.services.market_sync import BatchSyncService
from tests.utils.fake_gemini import FakeGeminiClient, create_mapping_response


def test_unit_db_writer_worker_us_ingest(test_settings):
    """Unit test: _db_writer_worker handles US_INGEST correctly."""
    service = BatchSyncService(start_workers=True)
    service.us_engine.ingest_facts = lambda t, d, s: None

    ticker = "AAPL"
    data = {"some": "data"}
    session_id = "test-session"
    service.db_queue.put(("US_INGEST", ticker, data, session_id))
    service.db_queue.join()
    assert service.session_stats["SUCCESS"] == 1


def test_unit_db_writer_worker_log_error(test_settings):
    """Unit test: _db_writer_worker handles LOG_ERROR correctly."""
    service = BatchSyncService(start_workers=True)
    service.db_queue.put(("LOG_ERROR", "US", "FAIL", "Some error"))
    service.db_queue.join()
    assert service.session_stats["ERROR"] == 1


def test_unit_ai_mapper_worker_map_tags(test_settings):
    """Unit test: _ai_mapper_worker processes tags and pushes to db_queue."""
    fake_response = create_mapping_response(
        [{"tag_id": "T0", "mapped_label": "NetSales", "reasoning": "Matches", "confidence": 0.9}]
    )
    fake_client = FakeGeminiClient([fake_response])
    service = BatchSyncService(start_workers=True)
    service.mapper.client = fake_client

    tags = [("Revenue", "Total Revenue")]
    service.ai_queue.put(("MAP_TAGS", "US", "AAPL", tags, "session-123"))
    service.ai_queue.join()
    service.db_queue.join()
    assert fake_client.models.call_count == 1


def test_unit_queue_unmapped_tags(test_settings):
    """Unit test: _queue_unmapped_tags identifies missing tags and queues them."""
    service = BatchSyncService(start_workers=False)
    ticker = "TEST_UNMAPPED"
    cik = "0000000001"

    # Pre-populate tickers to match the logic in _queue_unmapped_tags

    with duckdb.connect(str(service.us_engine.db_path)) as conn:
        conn.execute(
            "INSERT INTO tickers (ticker, cik, name) VALUES (?, ?, ?)", [ticker, cik, "Test Corp"]
        )

    service.us_engine.ingest_facts(
        ticker,
        {
            "cik": cik,
            "facts": {
                "us-gaap": {
                    "NewTag": {
                        "units": {
                            "USD": [
                                {
                                    "val": 100,
                                    "end": "2023-01-01",
                                    "accn": "A1",
                                    "fy": 2023,
                                    "fp": "FY",
                                    "form": "10-K",
                                    "filed": "2023-01-01",
                                }
                            ]
                        }
                    }
                }
            },
        },
        "session-1",
    )

    service._queue_unmapped_tags("US", ticker, "session-1")
    assert service.ai_queue.qsize() == 1
    task = service.ai_queue.get()
    assert task[0] == "MAP_TAGS"
    assert task[3][0][0] == "NewTag"
