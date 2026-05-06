from unittest.mock import MagicMock, patch

import pytest

from src.mappers.ai_mapper import AIMapper


@pytest.fixture
def mock_genai():
    with patch("src.mappers.ai_mapper.genai.Client") as mock:
        yield mock


def test_ai_mapper_map_tag_success(mock_genai, tmp_path):
    # Setup mock response
    mock_client_instance = mock_genai.return_value
    mock_response = MagicMock()
    mock_response.text = (
        '{"mappings": [{"tag_id": "T0", "mapped_label": "TotalAssets", '
        '"reasoning": "Standard mapping", "confidence": 0.99}]}'
    )
    mock_client_instance.models.generate_content.return_value = mock_response

    mapper = AIMapper()

    result = mapper.map_tag("US", "Assets", "Total assets of company", "session-123")

    assert result["mapped_label"] == "TotalAssets"
    assert result["reasoning"] == "Standard mapping"
    assert result["confidence"] == 0.99


def test_ai_mapper_parsing_error_retry(mock_genai):
    mock_client_instance = mock_genai.return_value

    # 1st call: Junk response (will trigger except block)
    # 2nd call: Valid JSON
    mock_response_fail = MagicMock()
    mock_response_fail.text = "This is not JSON"
    # We simulate an exception during the first iteration

    mock_response_success = MagicMock()
    mock_response_success.text = (
        '{"mappings": [{"tag_id": "T0", "mapped_label": "NetIncome", '
        '"reasoning": "Fixed", "confidence": 0.8}]}'
    )

    # Side effect for generate_content
    def side_effect(*args, **kwargs):
        if side_effect.call_count == 0:
            side_effect.call_count += 1
            raise Exception("429 Rate Limit")
        return mock_response_success

    side_effect.call_count = 0
    mock_client_instance.models.generate_content.side_effect = side_effect

    with patch("src.mappers.ai_mapper.settings") as mock_settings:
        mock_settings.LIGHT_GOOGLE_AI_MODELS = ["model-1", "model-2"]
        mock_settings.TARGET_LABELS = ["NetIncome", "TotalAssets"]

        mapper = AIMapper()
        result = mapper.map_tags_bulk("US", [("Profit", "Net profit")], "session-123")
        assert result[0]["mapped_label"] == "NetIncome"
        assert mock_client_instance.models.generate_content.call_count == 2
