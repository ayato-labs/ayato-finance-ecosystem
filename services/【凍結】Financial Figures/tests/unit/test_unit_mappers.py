from src.mappers.ai_mapper import AIMapper
from tests.utils.fake_gemini import FakeGeminiClient, create_mapping_response


def test_map_tags_batch_success():
    # Setup fake client with successful response
    fake_json = create_mapping_response(
        [{"tag_id": "T0", "mapped_label": "NetSales", "reasoning": "Match", "confidence": 0.9}]
    )
    fake_client = FakeGeminiClient([fake_json])
    mapper = AIMapper(client=fake_client)

    tags = [("Revenue", "Total revenue from sales")]
    results = mapper.map_tags_batch("US", tags, "test-model", "session-1")

    assert len(results) == 1
    assert results[0]["mapped_label"] == "NetSales"
    assert fake_client.models.call_count == 1


def test_map_tags_batch_resilience_split():
    """Test that a 'HUNG' batch is split and retried."""
    # Setup: 1st call hangs, 2nd and 3rd succeed (after split)
    resp_success_1 = create_mapping_response(
        [{"tag_id": "T0", "mapped_label": "NetSales", "reasoning": "Match"}]
    )
    resp_success_2 = create_mapping_response(
        [{"tag_id": "T1", "mapped_label": "OperatingProfit", "reasoning": "Match"}]
    )

    fake_client = FakeGeminiClient(
        [
            "__HUNG__",  # First try with 2 tags fails/hangs
            resp_success_1,  # Second try (Tag 0) succeeds
            resp_success_2,  # Third try (Tag 1) succeeds
        ]
    )

    # We need to set a small timeout in settings or mapper to trigger this fast.
    # For now, AIMapper uses 30s timeout in code, but our Fake simulates it
    # with a shorter delay if needed.
    # Actually, map_tags_batch handles the exception from executor.

    mapper = AIMapper(client=fake_client)
    tags = [("Rev", "Rev desc"), ("OP", "OP desc")]

    # We expect the mapper to handle the hang and split via map_tags_bulk
    # Use a short timeout to trigger the 'HUNG' logic quickly in tests
    results = mapper.map_tags_bulk("US", tags, "session-res", batch_size=2, timeout=0.1)

    assert len(results) == 2
    mapped_labels = [r["mapped_label"] for r in results]
    assert "NetSales" in mapped_labels
    assert "OperatingProfit" in mapped_labels
    # Call count: 1 (hang) + 1 (split part 1) + 1 (split part 2) = 3
    assert fake_client.models.call_count == 3


def test_map_tags_batch_invalid_json_chaos():
    """Chaos Test: Feed invalid JSON and ensure it handles it or retries."""
    fake_client = FakeGeminiClient(
        [
            "This is not JSON",
            create_mapping_response(
                [{"tag_id": "T0", "mapped_label": "Other", "reasoning": "Retry worked"}]
            ),
        ]
    )
    mapper = AIMapper(client=fake_client)

    tags = [("UnknownTag", "???")]
    results = mapper.map_tags_bulk("US", tags, "session-chaos", batch_size=1)

    assert len(results) == 1
    assert results[0]["mapped_label"] == "Other"
    assert fake_client.models.call_count == 2
