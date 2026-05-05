import re
import sys
import warnings
from typing import ClassVar

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from markdownify import markdownify as md

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
sys.setrecursionlimit(10000)


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
        try:
            return md(
                str(soup),
                heading_style="ATX",
                bullets="-",
                strip=["script", "style", "head"],
                table_conversion="github",
            )
        except (RecursionError, Exception):
            # 巨大すぎるHTMLの場合はプレーンテキストにフォールバック
            return soup.get_text(separator="\n", strip=True)

    def extract_all_sections(self, html_content: str, form_type: str = "10-K") -> dict[str, str]:
        """
        Unstructuredライブラリを使用して、HTMLをセクション（Item 1, 7等）ごとに分割する。
        """
        if not html_content:
            return {}

        try:
            from unstructured.partition.html import partition_html
            
            # 1. HTMLを要素（Title, NarrativeText等）に分解
            elements = partition_html(text=html_content)
            
            sections_found = {}
            current_section = "preamble"
            current_content = []
            
            # SEC書類のセクション見出しパターン (Item 1., Part I, etc.)
            item_regex = re.compile(r"^\s*(ITEM|PART)\s+[0-9A-Z]+[\.\:\s]", re.IGNORECASE)
            
            for el in elements:
                text = str(el).strip()
                if not text:
                    continue
                    
                # 見出しの検出
                if item_regex.match(text) and len(text) < 150:
                    # 前のセクションを保存
                    if current_content:
                        sections_found[current_section] = self.clean_text("\n".join(current_content))
                    
                    # キーの正規化 ("Item 1. Business" -> "item_1__business")
                    current_section = re.sub(r"[^a-z0-9]", "_", text.lower()).strip("_")
                    current_content = []
                else:
                    current_content.append(text)
            
            # 最後のセクションを保存
            if current_content:
                sections_found[current_section] = self.clean_text("\n".join(current_content))
                
            # 万が一分割に失敗した場合のフォールバック
            if len(sections_found) <= 1:
                logger.warning(f"Unstructured split yielded few sections ({len(sections_found)}). Falling back to full_content.")
                sections_found["full_content"] = self.clean_text(html_content)
                
            return sections_found

        except ImportError:
            logger.error("Unstructured library not found. Falling back to simple regex.")
            # 従来のフォールバックロジック（簡略化して維持）
            return {"full_content": self.clean_text(html_content)}
        except Exception as e:
            logger.exception(f"Critical error in EdgarParser: {e}")
            return {"full_content": self.clean_text(html_content)}


if __name__ == "__main__":
    parser = EdgarParser()
    test_html = (
        "<html><body><h1>Item 1. Business</h1><p>Our business is great.</p>"
        "<h1>Item 1A. Risk Factors</h1><p>Many risks.</p></body></html>"
    )
    print(parser.extract_all_sections(test_html, "10-K").keys())
