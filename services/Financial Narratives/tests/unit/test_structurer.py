import pytest
from unittest.mock import MagicMock, patch
from src.structurer import FilingStructurer

@pytest.mark.asyncio
async def test_extract_facts_basic():
    mock_api_key = "test_key"
    structurer = FilingStructurer(api_key=mock_api_key)
    
    # Mock response
    mock_response = MagicMock()
    mock_response.text = '{"capex": {"intent": "Expand production"}, "rd": null, "governance": null}'
    
    with patch.object(structurer.client.models, 'generate_content', return_value=mock_response):
        sections = {"business": "We are expanding our production capacity in 2025."}
        result = await structurer.extract_facts(sections)
        
        assert result["capex"]["intent"] == "Expand production"
        assert result["rd"] is None

@pytest.mark.asyncio
async def test_extract_facts_empty():
    structurer = FilingStructurer(api_key="test_key")
    result = await structurer.extract_facts({})
    assert result == {}

@pytest.mark.asyncio
async def test_extract_facts_error():
    structurer = FilingStructurer(api_key="test_key")
    with patch.object(structurer.client.models, 'generate_content', side_effect=Exception("API Error")):
        result = await structurer.extract_facts({"test": "data"})
        assert result == {}
