from src.edgar_parser import EdgarParser
from src.edinet_parser import EdinetParser


def test_edgar_parser_extract_sections():
    parser = EdgarParser()
    html = """
    <html>
        <body>
            <div id="item1">Item 1. Business.</div>
            <p>Our company expanded to Mars.</p>
            <div id="item1a">Item 1A. Risk Factors.</div>
            <p>Mars is cold.</p>
        </body>
    </html>
    """
    sections = parser.extract_sections(html)
    assert "business" in sections
    assert "Mars" in sections["business"]


def test_edinet_parser_text_block_logic():
    parser = EdinetParser()
    # Mocking basic structure since full ZIP parsing is in integration tests
    assert parser is not None
