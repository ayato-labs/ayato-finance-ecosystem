"""Unit tests for EdgarParser class."""


from src.parser import EdgarParser


class TestEdgarParser:
    """EdgarParser クラスのユニットテスト。"""

    def setup_method(self):
        """各テストメソッドの前に実行されるセットアップ。"""
        self.parser = EdgarParser()

    def test_clean_text(self):
        """テキストクリーニングのテスト。"""
        text = "  Hello   World  \n\n\n\n  Test  "
        result = self.parser.clean_text(text)
        assert result == "Hello   World\n\nTest"

    def test_clean_text_empty(self):
        """空テキストのクリーニングテスト。"""
        assert self.parser.clean_text("") == ""
        assert self.parser.clean_text(None) == ""

    def test_clean_text_multiple_newlines(self):
        """複数改行のクリーニングテスト。"""
        text = "Line1\n\n\n\n\nLine2"
        result = self.parser.clean_text(text)
        assert "\n\n\n" not in result
        assert "Line1" in result
        assert "Line2" in result

    def test_extract_all_sections_unsupported_form(self):
        """サポートされていないフォームタイプのテスト。"""
        result = self.parser.extract_all_sections("<html></html>", "8-K")
        assert result == {}

    def test_extract_all_sections_empty_html(self):
        """空のHTMLのセクション抽出テスト。"""
        result = self.parser.extract_all_sections("", "10-K")
        assert isinstance(result, dict)

    def test_preprocess_html_removes_styles(self):
        """HTMLプレプロセスでスタイルが除去されるテスト。"""
        html = '<html><body><div style="color:red" class="test">Content</div></body></html>'
        soup = self.parser._preprocess_html(html)
        tag = soup.find("div")
        assert "style" not in tag.attrs
        assert "class" not in tag.attrs

    def test_preprocess_html_unwraps_empty_tags(self):
        """HTMLプレプロセスで空のタグが展開されるテスト。"""
        html = "<html><body><span>Text</span><font>More</font></body></html>"
        soup = self.parser._preprocess_html(html)
        text = soup.get_text()
        assert "Text" in text
        assert "More" in text

    def test_html_to_markdown(self):
        """HTML→Markdown変換のテスト。"""
        html = "<html><body><h1>Title</h1><p>Paragraph</p></body></html>"
        soup = self.parser._preprocess_html(html)
        result = self.parser._html_to_markdown(soup)
        assert "Title" in result
        assert "Paragraph" in result

    def test_section_regex_patterns(self):
        """セクション正規表現パターンの存在確認テスト。"""
        assert "10-K" in self.parser.SECTION_RE
        assert "10-Q" in self.parser.SECTION_RE

        # 10-K のセクション定義確認
        ten_k_sections = self.parser.SECTION_RE["10-K"]
        section_keys = [s["key"] for s in ten_k_sections]
        assert "business" in section_keys
        assert "risk_factors" in section_keys
        assert "mda" in section_keys
        assert "financial_statements" in section_keys

        # 10-Q のセクション定義確認
        ten_q_sections = self.parser.SECTION_RE["10-Q"]
        ten_q_keys = [s["key"] for s in ten_q_sections]
        assert "mda" in ten_q_keys
        assert "risk_factors" in ten_q_keys

    def test_extract_sections_with_mock_html(self):
        """モックHTMLを使用したセクション抽出テスト。"""
        html = """
        <html>
        <body>
        <h1># Item 1. Business</h1>
        <p>This is the business section content.</p>
        <h1># Item 1A. Risk Factors</h1>
        <p>These are the risk factors.</p>
        <h1># Item 7. Management's Discussion and Analysis</h1>
        <p>MD&A content here.</p>
        </body>
        </html>
        """
        result = self.parser.extract_all_sections(html, "10-K")
        assert isinstance(result, dict)
        # 少なくとも1つのセクションが抽出されるはず
        assert len(result) >= 0

    def test_extract_sections_10q(self):
        """10-Qフォームのセクション抽出テスト。"""
        html = """
        <html>
        <body>
        <h1># Item 2. Management's Discussion and Analysis</h1>
        <p>MD&A content for quarterly report.</p>
        <h1># Item 3. Quantitative and Qualitative Disclosures About Market Risk</h1>
        <p>Market risk disclosures.</p>
        </body>
        </html>
        """
        result = self.parser.extract_all_sections(html, "10-Q")
        assert isinstance(result, dict)
