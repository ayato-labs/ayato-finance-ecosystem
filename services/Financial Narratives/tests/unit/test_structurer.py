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

# 注: extract_facts 自体は LLM クライアントを使用するため、
# ユーザー指示に従い Mock を使用しない場合は、有効な API キーが必要となる。
# 単体テストの範囲としては、ロジックを分離した上記関数群で十分カバーできる。
