from src.edgar_parser import EdgarParser

def test_parser_clean_text():
    parser = EdgarParser()
    # 前後の空白削除と連続する空行の圧縮を確認
    assert parser.clean_text("  hello  \n\n\nworld  ") == "hello\n\nworld"

def test_parser_extract_all_sections(sample_html):
    parser = EdgarParser()
    sections = parser.extract_all_sections(sample_html, "10-K")

    assert "business" in sections
    assert "risk_factors" in sections
    assert "mda" in sections
    # 内容が正しく抽出されているか (Markdown化されているか)
    assert "This is the business section content" in sections["business"]
    assert "This is the risk factors content" in sections["risk_factors"]
    assert "This is the MD&A content" in sections["mda"]

def test_parser_unsupported_form():
    parser = EdgarParser()
    sections = parser.extract_all_sections("<html></html>", "INVALID-FORM")
    assert sections == {}
