import json

from src.edinet.mapper import EDINETMapper
from src.edinet.reconciler import EDINETReconciler
from src.mappers.ai_mapper import AIMapper
from tests.utils.fake_gemini import FakeGeminiClient

# --- Constants for Testing ---
TICKER_TOYOTA = "7203"
VAL_1B = 1_000_000_000
VAL_1M = 1_000_000
VAL_10M = 10_000_000
VAL_20M = 20_000_000
VAL_100 = 100.0


# --- Reconciler Tests ---


def test_reconciler_rounding_match():
    reconciler = EDINETReconciler()
    # J: 1,000,000,500, E: 1,000,000,000 (Diff 500 < 1,000 tolerance)
    res = reconciler.reconcile_fact("NetSales", 1000000500, VAL_1B)
    assert res["strategy"] == "KEEP_EDINET"
    assert res["merged_val"] == VAL_1B


def test_reconciler_unit_scaling():
    reconciler = EDINETReconciler()
    # J: 1,000,000,000, E: 1,000,000 (1000x difference)
    res = reconciler.reconcile_fact("NetSales", VAL_1B, VAL_1M)
    assert res["strategy"] == "UNIT_SCALED_EDINET"
    assert res["merged_val"] == VAL_1B


def test_reconciler_override():
    reconciler = EDINETReconciler()
    # J: 10,000,000, E: 20,000,000 (Significant difference > 1M)
    res = reconciler.reconcile_fact("NetSales", VAL_10M, VAL_20M)
    assert res["strategy"] == "OVERRIDE_WITH_EDINET"
    assert res["merged_val"] == VAL_20M


# --- Mapper Normalization Tests ---


def test_mapper_normalization():
    mapper = EDINETMapper()
    raw_facts = [
        {"id": "tag1", "value": VAL_100, "unit": "JPY"},
        {"id": "tag2", "value": 200.0, "unit": "JPY"},
    ]
    tag_mapping = {"tag1": "NetSales"}  # tag2 is NOT mapped
    metadata = {
        "code": TICKER_TOYOTA,
        "disclosed_date": "2023-01-01",
        "accession_number": "S123",
        "session_id": "sess1",
        "fiscal_year": 2023,
        "fiscal_period": "FY",
    }

    normalized = mapper.normalize_facts(raw_facts, tag_mapping, metadata)
    assert len(normalized) == 1
    assert normalized[0]["code"] == TICKER_TOYOTA
    assert normalized[0]["label"] == "NetSales"
    assert normalized[0]["value"] == VAL_100
    assert normalized[0]["taxonomy"] == "JP_EDINET"


# --- AI Mapping Tests (No MagicMock) ---


def test_mapper_ai_mapping_with_fake():
    # Setup FakeGeminiClient with expected JSON response
    mock_mapping = {
        "mappings": [
            {
                "source_tag": "JP_EDINET:tag1",
                "mapped_label": "NetSales",
                "reasoning": "Test",
                "confidence": 0.9,
            }
        ]
    }
    fake_client = FakeGeminiClient(return_values=[json.dumps(mock_mapping)])

    # Inject fake client into Mapper
    ai_mapper = AIMapper()
    ai_mapper.client = fake_client

    mapper = EDINETMapper(ai_mapper=ai_mapper)

    results = mapper.map_edinet_tags([("tag1", "売上高")], "session1")
    assert len(results) == 1
    assert results[0]["mapped_label"] == "NetSales"
    assert fake_client.models.call_count == 1
