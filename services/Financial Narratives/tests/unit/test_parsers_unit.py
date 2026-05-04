import pytest
from src.edgar_parser import EdgarParser
from src.edinet_parser import EdinetParser

def test_edgar_parser_extract_sections():
    """EdgarParserの抽出ロジック（Markdownベース）の単体テスト"""
    parser = EdgarParser()
    html = """
    <html>
        <body>
            <div>Item 1. Business</div>
            <p>Our business is great.</p>
            <div>Item 1A. Risk Factors</div>
            <p>We might fail.</p>
        </body>
    </html>
    """
    sections = parser.extract_all_sections(html, "10-K")
    assert "business" in sections
    assert "risk_factors" in sections
    assert "Our business is great." in sections["business"]

def test_edgar_parser_invalid_form():
    """未対応のフォームタイプに対する挙動"""
    parser = EdgarParser()
    assert parser.extract_all_sections("<html></html>", "INVALID") == {}

def test_edinet_parser_parse_ixbrl():
    """EdinetParserのiXBRLタグ抽出の単体テスト"""
    parser = EdinetParser()
    # TAG_MAP にあるタグを模倣
    html = """
    <html>
        <body>
            <ix:nonNumeric name="jpcrp_cor:BusinessRisksTextBlock">
                リスク1: 競合他社
            </ix:nonNumeric>
            <ix:nonNumeric name="jpcrp_cor:ResearchAndDevelopmentActivitiesTextBlock">
                R&D投資を強化します
            </ix:nonNumeric>
        </body>
    </html>
    """
    results = parser.parse_ixbrl(html)
    assert "risk_factors" in results
    assert "rd" in results
    assert "リスク1: 競合他社" in results["risk_factors"]
    assert "R&D投資を強化します" in results["rd"]

def test_edinet_parser_empty_ixbrl():
    """iXBRLタグが見つからない場合"""
    parser = EdinetParser()
    html = "<html><body>No tags here</body></html>"
    results = parser.parse_ixbrl(html)
    assert results == {}
