import pytest
from src.structurer import FilingStructurer


def test_prepare_prompt_basic():
    """プロンプト作成の基本テスト (Mock不要)"""
    structurer = FilingStructurer(api_key="dummy_key")
    sections = {"business": "Expansion plan in 2025."}
    prompt = structurer._prepare_prompt(sections)

    assert "Expansion plan in 2025." in prompt
    assert "### Section: business" in prompt


def test_prepare_prompt_empty():
    """空の入力に対する挙動 (Mock不要)"""
    structurer = FilingStructurer(api_key="dummy_key")
    assert structurer._prepare_prompt({}) is None
    assert structurer._prepare_prompt({"empty": ""}) is None


def test_parse_response_valid():
    """正常なJSONレスポンスのパース (Mock不要)"""
    structurer = FilingStructurer(api_key="dummy_key")
    json_str = '{"capex": {"intent": "new factory"}, "rd": null, "governance": null}'
    result = structurer._parse_response(json_str)
    assert result["capex"]["intent"] == "new factory"


def test_parse_response_invalid():
    """異常なレスポンス（非JSON）に対するエラーハンドリング (Mock不要)"""
    structurer = FilingStructurer(api_key="dummy_key")
    with pytest.raises(ValueError, match="Invalid JSON response"):
        structurer._parse_response("Not a JSON string")


def test_parse_response_malformed():
    """不完全なJSONに対するエラーハンドリング (Mock不要)"""
    structurer = FilingStructurer(api_key="dummy_key")
    with pytest.raises(ValueError):
        structurer._parse_response('{"capex": {"intent": "unclosed"')


@pytest.mark.asyncio
async def test_extract_facts_real():
    """Gemini APIを実際に叩いて構造化を確認 (Mock不使用)"""
    import os

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        pytest.skip("GOOGLE_API_KEY not set in environment")

    structurer = FilingStructurer(api_key=api_key)
    sections = {
        "business": "当社は2025年に向けて、100億円の設備投資を行い、AI半導体の生産能力を倍増させる計画です。"
    }

    facts = await structurer.extract_facts(sections)
    assert facts is not None
    assert "capex" in facts
    assert "intent" in facts["capex"]
    # 意味的に正しいことが抽出されているか
    assert "100" in str(facts["capex"].get("amount", "")) or "投資" in str(facts["capex"])
