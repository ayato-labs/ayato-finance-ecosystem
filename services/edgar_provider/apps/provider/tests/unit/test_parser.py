import pytest
from edgar_provider.parser import EdgarParser

def test_clean_text():
    raw = "  Line 1 \n\n\n Line 2   "
    cleaned = EdgarParser.clean_text(raw)
    assert cleaned == "Line 1\n\nLine 2"

def test_extract_sections_10k():
    parser = EdgarParser()
    html = """
    <html>
        <body>
            <div>Item 1. Business</div>
            <p>This is the business section.</p>
            <div>Item 1A. Risk Factors</div>
            <p>These are the risks.</p>
            <div>Item 7. Management's Discussion and Analysis</div>
            <p>Analysis here.</p>
        </body>
    </html>
    """
    sections = parser.extract_all_sections(html, "10-K")
    
    assert "business" in sections
    assert "risk_factors" in sections
    assert "mda" in sections
    assert "business section" in sections["business"]
    assert "risks" in sections["risk_factors"]
    assert "Analysis" in sections["mda"]

def test_unsupported_form():
    parser = EdgarParser()
    sections = parser.extract_all_sections("<html></html>", "8-K")
    assert sections == {}
