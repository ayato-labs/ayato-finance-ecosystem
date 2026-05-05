import pytest
import json
import os
from src.storage import FinancialNarrativeStorage
from src.structurer import FilingStructurer
from dotenv import load_dotenv

load_dotenv()

@pytest.mark.asyncio
async def test_storage_zstd_robustness(test_data_dir):
    db_file = str(test_data_dir / "test_unit.duckdb")
    storage = FinancialNarrativeStorage(db_path=db_file)
    
    # 1. 極小データ
    meta = {"accessionNumber": "U001", "ticker": "T1", "form": "F", "filingDate": "2024-01-01"}
    storage.save_filing(meta, {"empty": ""})
    assert storage.get_sections("U001") == {"empty": ""}
    
    # 2. 辞書外データ
    weird_text = "TESTING ROBUSTNESS " + "🚀" * 10
    storage.save_filing({"accessionNumber": "U002", "ticker": "T2", "form": "F", "filingDate": "2024-01-01"}, {"w": weird_text})
    assert storage.get_sections("U002")["w"] == weird_text

def test_structurer_json_parsing_resilience():
    structurer = FilingStructurer(api_key="dummy")
    broken_llm_output = "Here is the result: ```json\n{\"thinking\": \"ok\", \"capex\": []}\n``` Hope this helps!"
    parsed = structurer._parse_json(broken_llm_output)
    assert parsed.get("thinking") == "ok"

@pytest.mark.asyncio
async def test_llm_actual_call():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        pytest.skip("GOOGLE_API_KEY is not set")
    
    structurer = FilingStructurer(api_key=api_key)
    sections = {"business_risk": "当社の主なリスクは、為替変動と半導体不足です。"}
    facts = await structurer.extract_facts(sections)
    
    assert isinstance(facts, dict)
    assert "thinking" in facts
