import pytest
from src.analyzer import EdgarAnalyzer, NarrativeAnalysis

@pytest.mark.asyncio
async def test_analyzer_mock(mocker):
    # Mocking genai client
    mock_client = mocker.patch("google.genai.Client")
    mock_instance = mock_client.return_value
    
    # Setting up a mock response with parsed attribute
    mock_response = mocker.Mock()
    mock_response.parsed = NarrativeAnalysis(
        capex_summary="High Capex planned for data centers.",
        rd_summary="Focus on AI chips.",
        governance_summary="Strong dividend policy.",
        key_quotes=["Quote 1"],
        sentiment_score=0.8
    )
    mock_instance.aio.models.generate_content = mocker.AsyncMock(return_value=mock_response)
    
    analyzer = EdgarAnalyzer(api_key="test_key")
    sections = {"mda": "test mda", "business": "test business"}
    
    result = await analyzer.analyze_narratives(sections)
    
    assert result.capex_summary == "High Capex planned for data centers."
    assert result.sentiment_score == 0.8
    assert mock_instance.aio.models.generate_content.called

def test_generate_prompt():
    analyzer = EdgarAnalyzer(api_key="test_key")
    sections = {"mda": "Management discussion content", "business": "Business summary"}
    prompt = analyzer._generate_prompt(sections)
    
    assert "Management discussion content" in prompt
    assert "Business summary" in prompt
    assert "Capex" in prompt
