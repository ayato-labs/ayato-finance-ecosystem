import pytest

from src.structurer import FilingStructurer


def test_chunk_text():
    structurer = FilingStructurer(api_key="fake")
    text = "A" * 50000
    chunks = structurer._chunk_text(text, max_chars=30000)
    assert len(chunks) == 2
    assert len(chunks[0]) == 30000
    # Overlap check
    assert chunks[1].startswith(text[28000:28100])


def test_parse_json_valid():
    structurer = FilingStructurer(api_key="fake")
    valid_json = '{"capex": {"amount": 100}, "rd": "AI Research"}'
    result = structurer._parse_json(valid_json)
    assert result["capex"]["amount"] == 100
    assert result["rd"] == "AI Research"


def test_parse_json_markdown():
    structurer = FilingStructurer(api_key="fake")
    md_json = '```json\n{"capex": 50}\n```'
    result = structurer._parse_json(md_json)
    assert result["capex"] == 50


def test_parse_json_invalid():
    structurer = FilingStructurer(api_key="fake")
    invalid_json = '{"capex": 100'  # Broken
    result = structurer._parse_json(invalid_json)
    assert result == {}


@pytest.mark.asyncio
async def test_extract_facts_mock(monkeypatch):
    import os

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        pytest.skip("GOOGLE_API_KEY not set in environment")

    structurer = FilingStructurer(api_key=api_key)
    sections = {
        "business": (
            "当社は2025年に向けて、100億円の設備投資を行い、AI半導体の生産能力を倍増させる計画です。"
        )
    }

    facts = await structurer.extract_facts(sections)
    assert facts is not None
