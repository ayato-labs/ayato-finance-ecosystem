import re
import sys
import warnings
from typing import ClassVar

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from loguru import logger
from markdownify import markdownify as md

# Increase recursion limit for complex SEC documents
sys.setrecursionlimit(5000)

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


class EdgarParser:
    """
    SEC 10-K/10-Q ドキュメントから正確に複数のセクションを抽出し、Markdown形式で出力するクラス
    """

    # セクション特定のためのパターン (Markdown化した後のテキストに対して適用)
    SECTION_RE: ClassVar[dict[str, list[dict]]] = {
        "10-K": [
            {
                "key": "business",
                "start": re.compile(r"^#*\s*Item\s*1[\s\.]*Business", re.IGNORECASE | re.MULTILINE),
            },
            {
                "key": "risk_factors",
                "start": re.compile(
                    r"^#*\s*Item\s*1A[\s\.]*Risk\s*Factors", re.IGNORECASE | re.MULTILINE
                ),
            },
            {
                "key": "unresolved_staff_comments",
                "start": re.compile(
                    r"^#*\s*Item\s*1B[\s\.]*Unresolved", re.IGNORECASE | re.MULTILINE
                ),
            },
            {
                "key": "mda",
                "start": re.compile(
                    r"^#*\s*Item\s*7[\s\.]*Management", re.IGNORECASE | re.MULTILINE
                ),
            },
            {
                "key": "market_risk",
                "start": re.compile(
                    r"^#*\s*Item\s*7A[\s\.]*Quantitative", re.IGNORECASE | re.MULTILINE
                ),
            },
            {
                "key": "financial_statements",
                "start": re.compile(
                    r"^#*\s*Item\s*8[\s\.]*Financial", re.IGNORECASE | re.MULTILINE
                ),
            },
            {
                "key": "governance",
                "start": re.compile(
                    r"^#*\s*Item\s*10[\s\.]*Directors", re.IGNORECASE | re.MULTILINE
                ),
            },
            {
                "key": "signatures",
                "start": re.compile(r"^#*\s*Signatures", re.IGNORECASE | re.MULTILINE),
            },
        ],
        "10-Q": [
            {
                "key": "mda",
                "start": re.compile(
                    r"^#*\s*Item\s*2[\s\.]*Management", re.IGNORECASE | re.MULTILINE
                ),
            },
            {
                "key": "market_risk",
                "start": re.compile(
                    r"^#*\s*Item\s*3[\s\.]*Quantitative", re.IGNORECASE | re.MULTILINE
                ),
            },
            {
                "key": "legal_proceedings",
                "start": re.compile(
                    r"^#*\s*Part\s*II.*Item\s*1[\s\.]*Legal", re.IGNORECASE | re.MULTILINE
                ),
            },
            {
                "key": "risk_factors",
                "start": re.compile(
                    r"^#*\s*Item\s*1A[\s\.]*Risk\s*Factors", re.IGNORECASE | re.MULTILINE
                ),
            },
        ],
    }

    @staticmethod
    def clean_text(text: str) -> str:
        if not text:
            return ""
        # 行ごとにトリミングを行い、過剰な空行を整理
        lines = [line.strip() for line in text.split("\n")]
        cleaned_text = "\n".join(lines)
        cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)
        return cleaned_text.strip()

    def _preprocess_html(self, html_content: str) -> BeautifulSoup:
        soup = BeautifulSoup(html_content, "lxml")
        # 不要なタグのunwrapまたは削除
        # スタイル指定がない、またはテキストのみのコンテナを優先的に処理
        for tag in soup(["span", "font", "div"]):
            if not tag.attrs:
                tag.unwrap()

        # 不要な属性の削除（変換に影響しないもの。Markdown変換時の負荷を下げる）
        for tag in soup.find_all(True):
            for attr in [
                "style",
                "class",
                "id",
                "width",
                "height",
                "border",
                "cellspacing",
                "cellpadding",
            ]:
                if attr in tag.attrs:
                    del tag.attrs[attr]

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
        ドキュメントから定義された全てのセクションを抽出し、辞書形式で返す
        """
        if form_type not in self.SECTION_RE:
            logger.warning(f"Unsupported form type: {form_type}")
            return {}

        soup = self._preprocess_html(html_content)
        full_markdown = self._html_to_markdown(soup)
        lines = full_markdown.split("\n")

        sections_found = {}
        definitions = self.SECTION_RE[form_type]

        # 各セクションの開始行を特定
        indices = {}
        for defn in definitions:
            key = defn["key"]
            pattern = defn["start"]
            for i, line in enumerate(lines):
                # 目次内のリンクを避ける(リンクがない、かつパターンにマッチ、かつ行が長すぎない)
                if (
                    pattern.search(line)
                    and len(line) < 250
                    and not re.search(r"\[.*\]\(#.*\)", line)
                ):
                    indices[key] = i
                    break

        # 特定したインデックスに基づいてテキストを切り出し
        for i, defn in enumerate(definitions):
            key = defn["key"]
            if key not in indices:
                continue

            start_idx = indices[key]
            # 次のセクションの開始、またはファイルの最後までを範囲とする
            end_idx = None
            for next_defn in definitions[i + 1 :]:
                next_key = next_defn["key"]
                if next_key in indices:
                    end_idx = indices[next_key]
                    break

            extracted_content = "\n".join(lines[start_idx:end_idx])
            sections_found[key] = self.clean_text(extracted_content)

        return sections_found
