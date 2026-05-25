import pytest
from unittest.mock import MagicMock, patch
from src.structurer import FilingStructurer


@pytest.mark.asyncio
async def test_extract_facts_integration_success(mocker):
    """LLMクライアントをモック化した正常系の結合テスト"""
    structurer = FilingStructurer(api_key="test_key")

    # Client.models.generate_content をモック化
    mock_response = MagicMock()
    mock_response.text = '{"capex": {"intent": "test"}, "rd": null, "governance": null}'

    with patch.object(structurer.client.models, "generate_content", return_value=mock_response):
        result = await structurer.extract_facts({"business": "some text"})
        assert result["capex"]["intent"] == "test"


@pytest.mark.asyncio
async def test_extract_facts_integration_fallback(mocker):
    """
    1番目のモデルが失敗し、2番目のモデルで成功するフォールバックの結合テスト。
    複数モデルにまたがる挙動を確認する。
    """
    structurer = FilingStructurer(api_key="test_key")
    structurer.models = ["model-1", "model-2"]

    mock_response = MagicMock()
    mock_response.text = '{"capex": {"intent": "success"}, "rd": null, "governance": null}'

    with patch.object(structurer.client.models, "generate_content") as mock_gen:
        # 1回目は失敗、2回目は成功をシミュレート
        mock_gen.side_effect = [Exception("Model 1 down"), mock_response]

        result = await structurer.extract_facts({"business": "text"})

        assert result["capex"]["intent"] == "success"
        assert mock_gen.call_count == 2


@pytest.mark.asyncio
async def test_extract_facts_integration_all_fail():
    """全てのモデルが失敗した場合の挙動"""
    structurer = FilingStructurer(api_key="test_key")
    structurer.models = ["model-1", "model-2"]

    with patch.object(
        structurer.client.models, "generate_content", side_effect=Exception("API Error")
    ):
        result = await structurer.extract_facts({"business": "text"})
        assert result == {}
