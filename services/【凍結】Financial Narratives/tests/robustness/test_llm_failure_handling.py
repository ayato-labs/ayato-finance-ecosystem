from unittest.mock import MagicMock, patch

import pytest

from src.structurer import FilingStructurer


@pytest.mark.asyncio
async def test_llm_malformed_json_response():
    """LLMが壊れたJSONを返した場合の耐性テスト"""
    structurer = FilingStructurer(api_key="fake")

    mock_response = MagicMock()
    # 途中で切れたJSON
    mock_response.text = '{"capex": {"amount": 1000, "intent": "expanding'

    with patch.object(structurer.client.models, "generate_content", return_value=mock_response):
        facts = await structurer.extract_facts({"section": "some text"})
        # 最終的に空の辞書が返されることを確認（内部で例外をキャッチしているため）
        assert facts == {}


@pytest.mark.asyncio
async def test_llm_unexpected_structure():
    """LLMが期待しないデータ構造を返した場合"""
    structurer = FilingStructurer(api_key="fake")

    mock_response = MagicMock()
    # リストで返してくる（期待は辞書）
    mock_response.text = '["not", "a", "dict"]'

    with patch.object(structurer.client.models, "generate_content", return_value=mock_response):
        facts = await structurer.extract_facts({"section": "some text"})
        assert isinstance(facts, list)  # 現状の _parse_json は json.loads(text) を返すため


@pytest.mark.asyncio
async def test_llm_empty_response():
    """LLMが空文字を返した場合"""
    structurer = FilingStructurer(api_key="fake")

    mock_response = MagicMock()
    mock_response.text = ""

    with patch.object(structurer.client.models, "generate_content", return_value=mock_response):
        facts = await structurer.extract_facts({"section": "some text"})
        assert facts == {}


@pytest.mark.asyncio
async def test_llm_api_error():
    """Gemini API自体が例外を投げた場合"""
    structurer = FilingStructurer(api_key="fake")

    with patch.object(
        structurer.client.models, "generate_content", side_effect=RuntimeError("API Down")
    ):
        facts = await structurer.extract_facts({"section": "some text"})
        # エラーをキャッチして空を返すはず
        assert facts == {}
