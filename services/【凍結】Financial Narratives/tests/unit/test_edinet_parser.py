from src.edinet_parser import EdinetParser


def test_edinet_parser_clean_text():
    parser = EdinetParser()
    assert parser.clean_text("  abc  \n\n\n\ndef  ") == "abc\n\ndef"


def test_edinet_parser_parse_ixbrl():
    parser = EdinetParser()
    # R&D section tag
    html = """
    <html>
        <body>
            <ix:nonNumeric name="jpcrp_cor:ResearchAndDevelopmentActivitiesTextBlock">
                研究開発の内容です。
            </ix:nonNumeric>
            <ix:nonNumeric name="jpcrp_cor:BusinessRisksTextBlock">
                リスクの内容です。
            </ix:nonNumeric>
        </body>
    </html>
    """
    sections = parser.parse_ixbrl(html)
    assert "rd" in sections
    assert "risk_factors" in sections
    assert "研究開発の内容です。" in sections["rd"]
    assert "リスクの内容です。" in sections["risk_factors"]


def test_edinet_parser_no_tags():
    parser = EdinetParser()
    html = "<html><body>No special tags here</body></html>"
    sections = parser.parse_ixbrl(html)
    assert sections == {}


def test_edinet_parser_broken_html():
    """壊れたHTMLでのパース"""
    parser = EdinetParser()
    html = "<ix:nonNumeric name='jpcrp_cor:BusinessRisksTextBlock'>Unclosed tag"
    # BeautifulSoup should handle this gracefully
    sections = parser.parse_ixbrl(html)
    assert "risk_factors" in sections
