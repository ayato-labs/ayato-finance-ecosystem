import os
import pytest
from src.mappers.ai_mapper import AIMapper

GEMINI_KEY = os.getenv("GEMINI_API_KEY")

@pytest.mark.skipif(not GEMINI_KEY, reason="GEMINI_API_KEY not set")
def test_aimapper_real_call():
    """Test real AI mapping call to verify Gemini connectivity and response schema."""
    mapper = AIMapper()
    tags = [("jppfs_cor:NetSales", "売上高")]
    
    # This will hit the real API
    results = mapper.map_tags_bulk(tags)
    
    assert len(results) == 1
    mapping = results["jppfs_cor:NetSales"]
    assert "mapped_label" in mapping
    assert "confidence" in mapping
    assert mapping["confidence"] >= 0.0

@pytest.mark.skipif(not GEMINI_KEY, reason="GEMINI_API_KEY not set")
def test_aimapper_adversarial_tags():
    """Test AI mapping with ambiguous or nonsensical tags."""
    mapper = AIMapper()
    tags = [("unknown:gibberish_tag_123", "!!! Nonsense !!!")]
    
    results = mapper.map_tags_bulk(tags)
    mapping = results["unknown:gibberish_tag_123"]
    
    # Even for nonsense, it should return a structured response (likely low confidence)
    assert "mapped_label" in mapping
    assert mapping["confidence"] < 0.5 or mapping["mapped_label"] == "Unknown"
