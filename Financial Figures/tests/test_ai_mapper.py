from unittest.mock import MagicMock, patch

import pytest

from src.mappers.ai_mapper import AIMapper


@pytest.fixture
def mapper():
    return AIMapper()


def test_get_system_instruction_edinet(mapper):
    instruction = mapper._get_system_instruction("EDINET")
    assert "JAPAN (EDINET / J-Quants)" in instruction
    assert "J-Quants V2 fields" in instruction
    assert "Profit" in instruction


def test_get_system_instruction_us(mapper):
    instruction = mapper._get_system_instruction("US")
    assert "MARKET CONTEXT: US (SEC / EDGAR)" in instruction


def test_map_tags_bulk_validation(mapper):
    # Mock the Gemini client to return a mix of valid and invalid labels
    with patch.object(mapper.client.models, "generate_content") as mock_gen:
        mock_response = MagicMock()
        mock_response.text = '{"mappings": [{"source_tag": "tag1", "mapped_label": "NetSales", "reasoning": "test"}, {"source_tag": "tag2", "mapped_label": "InvalidLabel", "reasoning": "test"}]}'
        mock_gen.return_value = mock_response

        tags = [("tag1", "desc1"), ("tag2", "desc2")]
        results = mapper.map_tags_bulk("EDINET", tags, "test-session")

        assert results[0]["mapped_label"] == "NetSales"
        assert (
            results[1]["mapped_label"] == "Other"
        )  # Should be normalized to Other because InvalidLabel is not in V2 labels


def test_resilience_split_logic(mapper):
    # Test that a 504 error triggers a split
    with patch.object(mapper.client.models, "generate_content") as mock_gen:
        # First call fails with 504, second and third (splits) succeed
        mock_gen.side_effect = [
            Exception("504 DEADLINE_EXCEEDED"),
            MagicMock(
                text='{"mappings": [{"source_tag": "tag1", "mapped_label": "NetSales", "reasoning": "test"}]}'
            ),
            MagicMock(
                text='{"mappings": [{"source_tag": "tag2", "mapped_label": "OperatingProfit", "reasoning": "test"}]}'
            ),
        ]

        tags = [("tag1", "desc1"), ("tag2", "desc2")]
        results = mapper.map_tags_bulk("EDINET", tags, "test-session")

        assert len(results) == 2
        assert results[0]["mapped_label"] == "NetSales"
        assert results[1]["mapped_label"] == "OperatingProfit"
        assert mock_gen.call_count == 3
