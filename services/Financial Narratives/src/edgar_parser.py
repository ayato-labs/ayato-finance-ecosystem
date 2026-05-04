import re
import warnings
from typing import ClassVar

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from markdownify import markdownify as md

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

class EdgarParser:
    """
    SEC 10-K/10-Q ドキュメントから網羅的にテキストセクションを抽出するクラス。
    特定の項目だけでなく、ドキュメント全体の定性情報を保持することを目指す。
    """

    # 主要セクションのヒント（これらは優先的に個別のキーとして抽出する）
    CORE_SECTIONS: ClassVar[list[str]] = [
        "Business",
        "Risk Factors",
        "Unresolved Staff Comments",
        "Management's Discussion and Analysis",
        "Quantitative and Qualitative Disclosures About Market Risk",
        "Financial Statements",
        "Directors, Executive Officers and Corporate Governance",
        "Executive Compensation",
        "Legal Proceedings",
    ]

    @staticmethod
    def clean_text(text: str) -> str:
        if not text:
            return ""
        lines = [line.strip() for line in text.split("\n")]
        cleaned_text = "\n".join(lines)
        cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)
        return cleaned_text.strip()

    def _preprocess_html(self, html_content: str) -> BeautifulSoup:
        soup = BeautifulSoup(html_content, "lxml")
        for tag in soup(["span", "font", "div"]):
            if not tag.attrs:
                tag.unwrap()
        for ix_tag in soup.find_all(lambda t: t.name.startswith("ix:")):
            ix_tag.unwrap()
        return soup

    def _html_to_markdown(self, soup: BeautifulSoup) -> str:
        return md(
            str(soup),
            heading_style="ATX",
            bullets="-",
            strip=["script", "style", "head"],
            table_conversion="github",
        )

    def extract_all_sections(self, html_content: str, form_type: str) -> dict[str, str]:
        """
        ドキュメントから網羅的にセクションを分割して抽出する。
        """
        soup = self._preprocess_html(html_content)
        full_markdown = self._html_to_markdown(soup)
        lines = full_markdown.split("\n")

        # 1. すべての "Item" ヘッダーを動的に検出する
        # パターン: "Item 1.", "Item 1A.", "PART I", "Item 7." 等
        item_pattern = re.compile(r"^#*\s*(?:Item|Part)\s*[0-9A-Z]+[\s\.]", re.IGNORECASE)

        indices = []

        for i, line in enumerate(lines):
            # 目次のリンクを除外するための簡易チェック
            is_item = item_pattern.match(line)
            is_short = len(line) < 200
            not_link = not re.search(r"\[.*\]\(#.*\)", line)
            if is_item and is_short and not_link:
                indices.append((line.strip("# ").strip(), i))

        # 2. 分割実行
        sections_found = {}
        for i, (label, start_idx) in enumerate(indices):
            # キーをクリーンに（"Item 1. Business" -> "item_1" または "business"）
            # ここでは将来的な検索性を考慮し、正規化したラベルをキーにする
            key = re.sub(r"[^a-z0-9]", "_", label.lower()).strip("_")

            end_idx = indices[i + 1][1] if i + 1 < len(indices) else None
            content = "\n".join(lines[start_idx:end_idx])
            sections_found[key] = self.clean_text(content)

        # 3. もし一つもセクションが見つからなかった場合のフォールバック（ドキュメント全量を保存）
        if not sections_found:
            sections_found["full_content"] = self.clean_text(full_markdown)

        return sections_found

if __name__ == "__main__":
    parser = EdgarParser()
    test_html = (
        "<html><body><h1>Item 1. Business</h1><p>Our business is great.</p>"
        "<h1>Item 1A. Risk Factors</h1><p>Many risks.</p></body></html>"
    )
    print(parser.extract_all_sections(test_html, "10-K").keys())
