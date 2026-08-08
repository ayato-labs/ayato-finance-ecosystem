import re
import sys
import warnings
from typing import ClassVar

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from loguru import logger
from markdownify import markdownify as md

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


class EdgarParser:
    """
    SEC 10-K（通期）/ 10-Q（四半期）の HTML ドキュメントをパースし、
    特定のセクション（例: 経営戦略、事業リスク、MD&A 等）を抽出・Markdown化するためのテキスト処理クラス。
    """

    # 10-K, 10-Q 形式ごとの対象セクションと、それらの開始位置を検出するための正規表現パターン定義。
    # Markdown変換後の見出し行（Item 1、Item 7等）をターゲットにします。
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
        """不要な改行コードの連続（3つ以上の連続改行など）や、行前後の余分な空白をトリムして整形します。"""
        if not text:
            return ""
        lines = [line.strip() for line in text.split("\n")]
        cleaned_text = "\n".join(lines)
        cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)
        return cleaned_text.strip()

    def _preprocess_html(self, html_content: str) -> BeautifulSoup:
        """HTMLの無駄な装飾タグや属性情報を削除し、構造をプレーンに整えパース効率を向上させます。"""
        original_limit = sys.getrecursionlimit()
        try:
            sys.setrecursionlimit(20000)
            soup = BeautifulSoup(html_content, "lxml")
            
            # スタイルを持たない単なるラッパー用の汎用タグを展開（unwrap）して中身のテキストだけを露出
            for tag in soup(["span", "font", "div"]):
                if not tag.attrs:
                    tag.unwrap()

            # 無効なアルファベット+数字の組み合わせのカスタム難読化タグや過剰ネストタグをアンラップ
            valid_tags = {"html", "head", "body", "table", "tr", "td", "th", "tbody", "thead", "tfoot", "div", "span", "font", "p", "a", "b", "i", "u", "s", "strong", "em", "h1", "h2", "h3", "h4", "h5", "h6", "img", "br", "hr", "li", "ul", "ol"}
            for tag in soup.find_all(lambda t: t.name and (":" in t.name or re.match(r"^[a-z0-9]{3,}$", t.name))):
                if tag.name not in valid_tags:
                    tag.unwrap()

            # HTMLタグのインラインCSSスタイルやクラス名などをすべて破棄
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

            return soup
        finally:
            sys.setrecursionlimit(original_limit)

    def _html_to_markdown(self, soup: BeautifulSoup) -> str:
        """プレーン化した HTML 要素を GitHub 互換形式のマークダウンテキストに一括変換します。"""
        original_limit = sys.getrecursionlimit()
        try:
            sys.setrecursionlimit(20000)
            return md(
                str(soup),
                heading_style="ATX",
                bullets="-",
                strip=["script", "style", "head"],
                table_conversion="github",
            )
        except (RecursionError, Exception) as e:
            logger.warning(f"Markdown conversion fell back to text extraction due to recursion depth or parsing issue: {e}")
            return soup.get_text(separator="\n\n")
        finally:
            sys.setrecursionlimit(original_limit)

    def extract_all_sections(self, html_content: str, form_type: str) -> dict[str, str]:
        """
        HTML本文を受け取り、特定の開示フォームタイプ（10-K/Q）に基づいて、
        各種章（セクション）ごとにマークダウンテキストを切り分けて抽出した辞書を返します。
        """
        if form_type not in self.SECTION_RE:
            logger.warning(f"Unsupported form type: {form_type}")
            return {}

        soup = self._preprocess_html(html_content)
        full_markdown = self._html_to_markdown(soup)
        lines = full_markdown.split("\n")

        sections_found = {}
        definitions = self.SECTION_RE[form_type]

        # 各セクション見出しがマークダウンの何行目から開始しているかをスキャン
        indices = {}
        for defn in definitions:
            key = defn["key"]
            pattern = defn["start"]
            for i, line in enumerate(lines):
                # 誤判定（目次ページのリンクアンカー行など）を防ぎつつ見出しを検索
                if (
                    pattern.search(line)
                    and len(line) < 250
                    and not re.search(r"\[.*\]\(#.*\)", line)
                ):
                    indices[key] = i
                    break

        # スキャン結果を元に、開始位置から次のセクションの開始位置までの行を切り抜き
        for i, defn in enumerate(definitions):
            key = defn["key"]
            if key not in indices:
                continue

            start_idx = indices[key]
            end_idx = None
            # 現在のセクションの次以降で、開始インデックスが存在する最も近いセクションを終了点とする
            for next_defn in definitions[i + 1 :]:
                next_key = next_defn["key"]
                if next_key in indices:
                    end_idx = indices[next_key]
                    break

            extracted_content = "\n".join(lines[start_idx:end_idx])
            sections_found[key] = self.clean_text(extracted_content)

        if not sections_found or all(not content for content in sections_found.values()):
            cleaned_full = self.clean_text(full_markdown)
            if cleaned_full:
                sections_found["full_text"] = cleaned_full

        return sections_found

